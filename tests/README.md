# Running the tests

From the project root:

```powershell
python -m unittest discover -s tests -v
```

The integration class needs permission to open and connect to localhost TCP sockets. It explicitly skips only on Windows WinError10013. A skip is **not a pass**. Outside that restricted environment all seven integration methods should run; investigate any failures before demonstrating the system.

Optional portable firmware-rule tests, if g++ is installed:

```powershell
g++ -std=c++11 -Wall -Wextra -pedantic tests/test_firmware_rules.cpp -o "$env:TEMP\smart-lab-rules.exe"
if ($LASTEXITCODE -eq 0) { & "$env:TEMP\smart-lab-rules.exe" }
```

On the authoring host, compilation and execution both exited0 with no warnings/output. This checks assertions for threshold activation/clearing, hysteresis, invalid readings, debounce and timer wrap. It does not compile the Arduino/Wi-Fi/DHT driver or test physical hardware.

`results.txt` is the captured final Python test output. See `docs/test-results.md` for the Windows results and remaining bench checks.
