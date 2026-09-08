std_msgs/Header header
uint64 sequence
string source

uint8 CLEAR=0
uint8 PATH=1
uint8 WARNING=2
uint8 WARNING_HOLD=3
uint8 CRITICAL=4
uint8 UNKNOWN=5
uint8 risk_level

uint8 OFF=0
uint8 STEADY=1
uint8 STEADY_HOLD=2
uint8 PULSE=3
uint8 pattern

bool active
float32 normalized_magnitude
string reason
