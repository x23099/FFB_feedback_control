std_msgs/Header header
bool has_sequence
uint64 sequence
string source
string output_mode
string action
bool command_active
bool output_active
float32 requested_magnitude
float32 applied_magnitude
uint8 pattern

# Applied directional force. Zero when output is inactive.
int8 direction

string reason
bool fault
