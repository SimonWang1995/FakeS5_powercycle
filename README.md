Baidu_FakeS5
==============

## Version
`Rev: 1.1`

---

## Description
Baidu Fake-S5 Power Cycle Test Tool

---

## Script Process

    1. SUT: 复制SIT-Power-CycleTest-master脚本到SUT端,执行./PowerCycleTest.sh –c xx –accycle –system 
    2. Client: 复制此脚本到Client端。
    3. Client: 修改 `config.ini` 文件。 
    4. Client: 手動執行此腳本開始测试。
    5. Client: `reports` 目錄下檢查測試結果。
    6. SUT: `reports` 目錄下檢查測試結果。

## Usage

  - 可以使用 Help 信息來獲取更多有關腳本的使用方法。

    ```bash
    $ python run.py --help
    ```

  - 下面範例中會為每一個參數做解釋。

    - 以下為完整的測試命令：

      ```bash
      $ python run.py -H <BMCIP> -U <USERNAME> -P< PASSWD> power_downup -c 500 -d 180 -i 10
      ```

    - **`-H`** Remote SUT BMC IP。
    - **`-U, --username`** SUT BMC 用户名
    - **`-P, --passwd`** SUT BMC 密码
    - **`-c, --cycle`** Cycle次數。
    - **`-d, --delay`** poweroff->poweron delay时间
    - **`-i, --interval`** ping smartnic ip interval

  - 修改 `config.ini` 教學

    ```
    [HOST]
    ip = 172.17.0.62 # SUT OS IP
    osboot_timeout = 600 # 开机到进入OS超时时间
    osdelay = 480  # 进入OS后停留时间

    [CHECK_IP] # 每圈检查IP
    bf2_bmcip = 172.17.0.63
    bf2_osip = 172.17.0.62
    ```

---

## Reports

  - 可以在此目錄下 `reports/*.log` 檢查測試結果。

---