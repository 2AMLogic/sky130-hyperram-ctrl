"""Aggregates every controller bench into one cocotb module, because a
`klt functional-verification` request names a single testbench module
(flow/functional-verification-ctrl.json). `make -C verification/ctrl` runs the
modules separately; both run the same tests."""
from test_random_traffic import *             # noqa: F401,F403
from test_row03_command_address import *      # noqa: F401,F403
from test_row04_latency import *              # noqa: F401,F403
from test_row05_bursts import *               # noqa: F401,F403
from test_row06_write_mask import *           # noqa: F401,F403
from test_row07_register_space import *       # noqa: F401,F403
from test_row08_power_up import *             # noqa: F401,F403
from test_row09_max_cs_low import *           # noqa: F401,F403
from test_row10_rwds_extra_latency import *   # noqa: F401,F403
from test_row13_no_calibration import *       # noqa: F401,F403
from test_row15_host_interface import *       # noqa: F401,F403
from test_row16_host_bursts import *          # noqa: F401,F403
