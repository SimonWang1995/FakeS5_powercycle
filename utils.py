import subprocess
import logging
import time
import shutil
import sys
import os
import datetime
__version__ = '0.1.0'


def clear_reports(logpath, assumeyes):
    """clear_reports(logpth, assumeyes)

    Description:
        Clear log path file

    Usage:
        clear_reports(logpath, "Parameter assumeyes")

    Parameters:
        logpath       - log path
        assumeyes - assume yes

    Return:
        None
    """
    if os.path.exists(logpath):
        if os.listdir(logpath):
            if not assumeyes:
                ans = input("WARNING: Reposts is exists, Delete all reports [y/n]")
                if ans.lower() not in ['y', 'yes']:
                    ans1 = input("Are you sure want to continue? [Y|N]:")
                    if ans1.lower() not in ['y', 'yes']:
                        exit(255)
            shutil.rmtree(logpath)
            os.makedirs(logpath)
    else:
        os.makedirs(logpath)


def exec_command(command, silent=True, ignore=False, asyncflag=False):
    """exec_command(command, silent=True, ignore=False, async=False)

    Description:
        Open a subprocess via Popen, into the OS, to execute a command

    Usage:
        result = exec_command("ls -la")

    Parameters:
        command - Command to pass to the OS as a string
        silent  - Flag to enable (False) or disable (True) logging
                  Default: True
        ignore  - Flag to log (False) or not log (True) errors (stderr)
        async   - Return subprocess Process ID

    Return:
        stdout  - Return the results of the command executed as a list
    """
    logging.debug("Run Command: " + command)
    p = subprocess.Popen(command.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if asyncflag:
        return p.pid
    stdout, stderr = p.communicate()
    if not silent:
        logging.info(stdout)
    if p.returncode != 0 and not ignore:
        logging.error(stderr)
        raise NameError('%s failed: %s ' % (command, stderr))
    return stdout.decode()


def print_help_exit(parser, error_message):
    """print_help_exit(parser, error_message)

    Description:
        Log an error_message then exit 1

    Usage:
        print_help_exit(parser, "Parameter parser error message")

    Parameters:
        parser       - Options object
        error-mesage - Error message to log

    Return:
        Exit Code 1
    """
    logging.error(error_message)
    parser.print_help()
    sys.exit(1)


def short_ping(ip):
    """short_ping(ip)

    Description:
        Short ping test code.  Returns True if ip responds

    Usage:
        if short_ping(console_IP):

    Parameters:
        ip    - IP address to attempt to ping as a string

    Return:
        True / False
    """
    try:
        return not subprocess.call(['ping', '-c 2', ip], stdout=open(os.devnull, 'wb'))
    except subprocess.CalledProcessError as e:
        logging.error(e.output)

    return False


def ping_test(ip):
    """ping_test(ip)

    Description:
        Retry ping test code.  Returns True if ip and responds will retry 5 times before returning
        a failure response

    Usage:
        if ping_test(console_IP):

    Parameters:
        ip    - IP address to attempt to ping as a string

    Return:
        True / False
    """
    for _ in range(5):
        rcode = short_ping(ip)
        if rcode:
            return rcode
        if _ == 4 and not rcode:
            return rcode
        time.sleep(5)


def init_simple_logging(logFile):
    """init_simple_logging(logFile)

    Description:
        Initiate logging with file_name as argument. No special treatment given to
        stdout/err like the larger logging function below.

    Usage:
        init_simple_logging("/var/log/example.log")

    Parameters:
        logFile  - File name of the log file to open

    Return:
        None
    """
    logging.basicConfig(filename=logFile, level=logging.INFO, format='%(asctime)s [%(levelname)s] | %(message)s',
                        datefmt='%Y-%m-%dT%H:%M:%S')
    logging.info('Logger initialized in file %s\n' % logFile)


def initiate_logging(logFile):
    """initiate_logging(logFile)

    Description:
        Helper function to initiate logging and set up multiple logging streams.
        Allows for generation of local tests logs as well as stdout and stderr
        from parent shell

        1. The local file will collect all information from DEBUG to the standard
           INFO
        2. stdout(parent) will capture all output sent to the screen including
           ERROR
        3. stderr(parent) will only collect ERROR
        4. DEBUG is only collected in the local log.

    Usage:
        initiate_logging("/var/log/example.log")

    Parameters:
        logFile  - File name of the log file to open

    Return:
        None
    """
    format = logging.Formatter('%(asctime)s [%(levelname)s] | %(message)s', datefmt='%Y-%m-%dT%H:%M:%S')
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    file = logging.FileHandler(logFile)
    file.setFormatter(format)
    root.addHandler(file)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(format)
    root.addHandler(console)
    console2 = logging.StreamHandler()
    console2.setLevel(logging.WARNING)
    console2.setFormatter(format)
    root.addHandler(console2)
    logging.info('Logger initialized with file %s' % logFile)


def get_local_logger():
    logging.basicConfig(filename='stdout.log', format='[%(module)s %(lineno)s]%(asctime)s: %(message)s',
                        level=logging.INFO)
    return logging.getLogger('audit')


def timeout(ip, seconds, count):
    """timeout(ip, seconds, count)

    Description:
        This method will ping test IP and return if successful. If not, will
        sleep for <seconds> and retry.  If unsuccessful, will retry the
        sleep/ping cycle for <count> times

    Usage:
        result = timeout("192.168.1.1", 120, 10)

    Parameters:
        ip      - IP address to attempt ping
        seconds - Sleep time between loops
        count   - Number of loops

    Return:
        True / False
    """
    for _ in range(count):
        if ping_test(ip):
            logging.info('%s is responding to ping, continuing...' % ip)
            return True
        logging.info('%s not responding to ping, sleeping %s' % (ip, seconds))
        time.sleep(seconds)

    logging.error('%s did not come back, exiting...' % ip)
    return False


def putlog_to_file(file_name, info):
    """putlog_to_file(file_name, contents)

        Description:
            add <contents> to <file_name>
            NOTE: This is a append write

        Usage:
            putlog_to_file("/var/log/some.log", sel_dump)

        Parameters:
            file_name -- Destination file name
            contents  -- Data to be written

        Return:
            None
        """
    with open(file_name, 'a') as f:
        print(str(datetime.datetime.now()) + ': ' + str(info), file=f)


def write_to_file(file_name, contents):
    """write_to_file(file_name, contents)

    Description:
        Write <contents> to <file_name>
        NOTE: This is a destructive write

    Usage:
        write_to_file("/var/log/some.log", sel_dump)

    Parameters:
        file_name -- Destination file name
        contents  -- Data to be written

    Return:
        None
    """
    with open(file_name, 'w') as fh:
        fh.write(contents)


def read_from_file(file_name):
    """read_from_file(file_name)

    Description:
        Read <contents> from <file_name>

    Usage:
        read_from_file("/var/log/some.log")

    Parameters:
        file_name -- Source file name

    Return:
        contents  -- Data that was read
    """
    with open(file_name, 'r') as fh:
        contents = fh.read()
        return contents

