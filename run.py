import os
import sys
import logging
import time
import queue
from threading import Thread
import subprocess
from argparse import ArgumentParser
from utils import initiate_logging, short_ping, exec_command, timeout, putlog_to_file, clear_reports
import version
from lib.parserconfig import HOST_IP, OSBOOT_TIMEOUT, OSDELAY, checkip_conf
from lib.exceptions import PingIpFail, OsBootTimeOut
prog = os.path.basename(__file__)
LOGPATH = "reports"
capabilities = ["oem_power_downup", 'oem_powercycle', 'power_downup', 'powercycle']
stop_monitorflag = False
ignore_pserr = False  # Ignore oem power status code error, programs continue
ipUP = 'Up'
ipDown = 'Down'


def ping_test(check_ipdict, cycle, exp):
    logging.info("Check BF2_NIC ip status...")
    for name, ip in check_ipdict.items():
        PING_LOG = lambda msg: putlog_to_file(os.path.join(LOGPATH, ip + "_ping.log"), msg)
        PING_SUMMARY = lambda msg: putlog_to_file(os.path.join(LOGPATH, ip + "_ping_Summary.log"), msg)
        res, ret = subprocess.getstatusoutput('ping -c 2 ' + ip)
        state = ipUP if res == 0 else ipDown
        PING_LOG("Cycle# {0} >>>SUT {1} <<<\n".format(str(cycle), exp) + ret)
        # PING_LOG("\n" + ret)
        if state == exp:
            PING_SUMMARY("PASS, Cycle#{0} SUT {1} {2} {3} status is: {4}, Expect: {1}".format(cycle, exp, name, ip, state))
            logging.info("{0} {1} status is: {2}, Expect: {3} ".format(name, ip, state, exp))
        else:
            PING_SUMMARY("FAIL, Cycle#{0} SUT {1} {2} {3} status is: {4}, Expect: {1}, "
                         "Pls see {2}_ping.log for details".format(cycle, exp, name, ip, state))
            logging.error("{0} {1} status is: {2} does not match Expect: {3} , Pls see {1}_ping.log for details".format(
                name, ip, state, exp))
            raise RuntimeError('FAIL {0} {1} status does not match expectations'.format(name, ip))


def ipmonitor(ip, interval):
    global stop_monitorflag
    PING_LOG = lambda msg: putlog_to_file(os.path.join(LOGPATH, ip + "_ping.log"), msg)
    PING_SUMMARY = lambda msg: putlog_to_file(os.path.join(LOGPATH, ip + "_ping_Summary.log"), msg)
    while True:
        if stop_monitorflag == True:
            break
        ret, res = subprocess.getstatusoutput("ping -c 2 " + ip)
        PING_LOG("="*20 + "\n" + res)
        if ret:
            PING_SUMMARY("{0} not responding to ping, Pls see {0}_ping.log for details".format(ip))
            break
        else:
            PING_SUMMARY(ip + " is responding to ping, continuing...")
        time.sleep(interval)


def start_ipmonitors(checkip_conf, interval):
    logging.info("Start BF2_NIC ip monitor thread...")
    thread_list = []
    for name, ip in checkip_conf.items():
        logging.info("{0} {1} monitor thread start".format(name, ip))
        Monitor = Thread(target=ipmonitor, args=(ip, interval), name=name)
        Monitor.start()
        thread_list.append(Monitor)
    return thread_list


def chk_ipmonitor(thread_list):
    logging.info("Check BF2_NIC ipmonitor thread...")
    for thread in thread_list:
        if thread.isAlive() == True:
            logging.info("{0} {1} Monitor Thread isAlive".format(thread.name, checkip_conf[thread.name]))
        else:
            logging.error("{0} {1} Monitor Thread Dead, Pls see {1}_ping.log for details".format(
                thread.name, checkip_conf[thread.name]))
            raise RuntimeError("FAIL {0} {1} Monitor Thread Dead, Pls see {1}_ping.log for details".format(
                thread.name, checkip_conf[thread.name]))


def stop_ipmonitors(thread_list):
    global stop_monitorflag
    stop_monitorflag = True
    for thread in thread_list:
        if thread.isAlive() == True:
            thread.join()


def chk_oempowerstatus(expcode):
    logging.info("Check OEM Power status code...")
    OEM_POWERSTATE = IPMI + "raw 0x30 0x03 0x61 0x7e 0x00"
    status_dict = {"00": "S0", "04": "Fake-S5", "05": 'S5'}
    res = exec_command(OEM_POWERSTATE)
    statecode = res.split()[-1].strip()
    if statecode == expcode:
        logging.info("Current Power Status Code: {0}, Expect Code [{1}: {2}]".format(statecode, expcode, status_dict[expcode]))
    else:
        logging.error("Current Power Status Code: {0}, Expect Code [{1}: {2}]".format(statecode, expcode, status_dict[expcode]))
        if not ignore_pserr:
            raise RuntimeError("FAIL Power Status Code does not match expectations")


def wait_osboot():
    logging.info("Waitting OS Boot and IP Up...")
    if not timeout(HOST_IP, 60, OSBOOT_TIMEOUT // 60):
        raise TimeoutError("FAIL OS Boot or IP Up TimeOut {0}" + str(OSBOOT_TIMEOUT))
    logging.info("OS Boot Success")


def oem_power_downup():
    cycle = args['cycle']
    delay = args['delay']
    IPMI = "ipmitool -I lanplus -H {bmcip} -U {username} -P {passwd} ".format(**args)
    OEM_POWEROFF = IPMI + "raw 0x30 0x02 0x61 0x7e 0x00 0"
    OEM_POWERON = IPMI + "raw 0x30 0x02 0x61 0x7e 0x00 1"
    OEM_POWERSTATE = IPMI + "raw 0x30 0x03 0x61 0x7e 0x00"
    for i in range(1, cycle+1):
        logging.info("=================== Cycle# {0} ==================".format(str(i)))
        exec_command(OEM_POWEROFF, silent=False)
        time.sleep(delay)
        chk_oempowerstatus('05')
        ping_test(checkip_conf, i, ipDown)
        exec_command(OEM_POWERON)
        # logging.info("Waitting OS BOOT")
        wait_osboot()
        chk_oempowerstatus('00')
        ping_test(checkip_conf, i, ipUP)
        logging.info("Waiting {0} seconds for OS log Collection".format(str(OSDELAY)))
        time.sleep(OSDELAY)  # Wait OS Auto Collect log


def oem_powercycle():
    cycle = args['cycle']
    delay = args['delay']
    IPMI = "ipmitool -I lanplus -H {bmcip} -U {username} -P {passwd} ".format(**args)
    OEM_POWERCYCLE = IPMI + "raw 0x30 0x02 0x61 0x7e 0x00 2"
    OEM_POWERSTATE = IPMI + "raw 0x30 0x03 0x61 0x7e 0x00"
    for i in range(1, cycle+1):
        logging.info("===================Cycle# {0} ==================".format(str(i)))
        exec_command(OEM_POWERCYCLE, silent=False)
        logging.info("Sleep " + str(delay))
        time.sleep(delay)
        ping_test(checkip_conf, i, ipDown)
        wait_osboot()
        chk_oempowerstatus('00')
        ping_test(checkip_conf, i, ipUP)
        logging.info("Waiting {0} seconds for OS log Collection".format(str(OSDELAY)))
        time.sleep(OSDELAY)  # Wait OS Auto Collect log


def power_downup():
    cycle = args['cycle']
    interval = args['interval']
    delay = args['delay']
    IPMI = "ipmitool -I lanplus -H {bmcip} -U {username} -P {passwd} ".format(**args)
    POWER_OFF = IPMI + 'power off'
    POWER_ON = IPMI + 'power on'
    OEM_POWERSTATE = IPMI + "raw 0x30 0x03 0x61 0x7e 0x00"
    monitorthread_list = start_ipmonitors(checkip_conf, interval)
    try:
        for i in range(1, cycle+1):
            logging.info("===================Cycle# {0} ==================".format(str(i)))
            exec_command(POWER_OFF, silent=False)
            logging.info("Sleep " + str(delay))
            time.sleep(delay)
            chk_oempowerstatus('04')
            chk_ipmonitor(monitorthread_list)
            exec_command(POWER_ON, silent=False)
            wait_osboot()
            chk_oempowerstatus('00')
            chk_ipmonitor(monitorthread_list)
            logging.info("Waiting {0} seconds for OS log Collection".format(str(OSDELAY)))
            time.sleep(OSDELAY)  # Wait OS Auto Collect log
    #except Exception as e:
    #    logging.error(e)
    finally:
        stop_ipmonitors(monitorthread_list)


def powercycle():
    cycle = args['cycle']
    interval = args['interval']
    IPMI = "ipmitool -I lanplus -H {bmcip} -U {username} -P {passwd} ".format(**args)
    POWER_CYCLE = IPMI + 'power cycle'
    OEM_POWERSTATE = IPMI + "raw 0x30 0x03 0x61 0x7e 0x00"
    monitorthread_list = start_ipmonitors(checkip_conf, interval)
    try:
        for i in range(1, cycle+1):
            logging.info("=================== Cycle# {0} ==================".format(str(i)))
            exec_command(POWER_CYCLE, silent=False)
            time.sleep(20)
            wait_osboot()
            chk_oempowerstatus('00')
            chk_ipmonitor(monitorthread_list)
            logging.info("Waiting {0} seconds for OS log Collection".format(str(OSDELAY)))
            time.sleep(OSDELAY) # Wait OS Auto Collect log
    # except Exception as e:
    #     logging.error(e)
    finally:
        stop_ipmonitors(monitorthread_list)


def _argparse():
    parent_parser = ArgumentParser(add_help=False)
    parent_parser.add_argument("-H", metavar='', dest='bmcip', help="IPv4 address, or [IPv6 address]", required=True)
    parent_parser.add_argument("-V", '-v', action='version', version="%(prog)s version: {0}".format(version.Version),
                               help="show program's version number and exit")
    parent_parser.add_argument("-U", '--username', metavar='USERNAME', help="local username", required=True)
    parent_parser.add_argument("-P", '--passwd', metavar='PASSWORD', help="password", required=True)
    parent_parser.add_argument('-y', '--assumeyes',
                        action='store_true',
                        help='answer yes for all questions')
    parent_parser.add_argument('-D', '--debug', action='store_true', help='Enable Debug')

    parser = ArgumentParser(usage='%(prog)s [-h] [-V] [-H <HOST>] [-p <port>] -U <username> -P <password> [-j] <command> [parameter1] [parameter2]',
                                     parents=[parent_parser])

    subparsers = parser.add_subparsers()
    oem_power_downup_parser = subparsers.add_parser("oem_power_downup")
    oem_power_downup_parser.add_argument('-c', '--cycle', dest='cycle', type=int, default=500,
                                        help="Cycle Times(Default: %(default)s)")
    oem_power_downup_parser.add_argument('-d', '--delay', dest='delay', type=int, default=20,
                                        help="off to on delay time(Default: %(default)s)")
    oem_power_downup_parser.set_defaults(action=("oem_power_downup", oem_power_downup))

    oem_powercycle_parser = subparsers.add_parser("oem_powercycle")
    oem_powercycle_parser.add_argument('-c', '--cycle', dest='cycle', type=int, default=500,
                                       help="Cycle Times(Default: %(default)s)")
    oem_powercycle_parser.add_argument('-d', '--delay', dest='delay', type=int, default=20,
                                       help="down to ping BS2_BMCIP delay time(Default: %(default)s)")
    oem_powercycle_parser.set_defaults(action=("oem_powercycle", oem_powercycle))

    power_downup_parser = subparsers.add_parser("power_downup")
    power_downup_parser.add_argument('-c', '--cycle', dest='cycle', type=int, default=500,
                                    help="Cycle Times(Default: %(default)s)")
    power_downup_parser.add_argument('-d', '--delay', dest='delay', type=int, default=180,
                                    help="off to on delay time(Default: %(default)s)")
    power_downup_parser.add_argument('-i', '--interval', dest='interval', type=int, default=10,
                                     help="ping ip interval(Default: %(default)s)")
    power_downup_parser.set_defaults(action=("power_downup", power_downup))

    powercycle_parser = subparsers.add_parser("powercycle")
    powercycle_parser.add_argument('-c', '--cycle', dest='cycle', type=int, default=500, help="Cycle Times(Default: %(default)s)")
    powercycle_parser.add_argument('-i', '--interval', dest='interval', type=int, default=1,
                                     help="ping ip interval(Default: %(default)s)")
    powercycle_parser.set_defaults(action=("powercycle", powercycle))

    group1 = parser.add_argument_group('oem power cycle',
                                       'python3 %(prog)s -H <bmcip> -P <user> -U <passwd> oem_powercycle -c 2 -d 20')
    group2 = parser.add_argument_group('oem power down up',
                                       'python3 %(prog)s -H <bmcip> -P <user> -U <passwd> oem_power_downup -c 2 -d 20')
    group3 = parser.add_argument_group('powercycle',
                                       'python3 %(prog)s -H <bmcip> -P <user> -U <passwd> powercycle -c 2 -i 1')
    group4 = parser.add_argument_group('power down up',
                                       'python3 %(prog)s -H <bmcip> -P <user> -U <passwd> power_downup -c 2 -d 180 -i 10')
    return parser.parse_args().__dict__


if __name__ == '__main__':
    args = _argparse()
    #print(args)
    debug = args['debug']
    assumeyes = args['assumeyes']
    if 'action' not in args:
        print("Usage: {0} -H <BMC IP> -U <Username> -P <Password> <Command>".format(prog))
        print("Command suported list " + str(capabilities))
        print("Use -h for more help " + str(capabilities))
    else:
        IPMI = "ipmitool -I lanplus -H {bmcip} -U {username} -P {passwd} ".format(**args)
        clear_reports(LOGPATH, assumeyes)
        (name, func) = args['action']
        logFile = os.path.join(LOGPATH, "%s.log" % name)
        initiate_logging(logFile)
        func()
