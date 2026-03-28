# messages

Plugin-defined message payload headers live here.

Each header defines a C struct following the Basilisk naming convention
`<Name>MsgPayload`. At build time, `bsk_generate_messages()` in
`CMakeLists.txt` auto-generates SWIG bindings for each payload so they
are accessible from Python.

Example:

```c
typedef struct {
    double density;
    int32_t modelValid;
} CustomAtmStatusMsgPayload;
```
