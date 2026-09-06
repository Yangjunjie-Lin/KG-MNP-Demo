# Environment pointer v1

An environment manifest is policy; its pointer is mutable control-plane state.
Pointer generation and hash are CAS inputs, with `NO_RELEASE_SELECTED` as the
initial state and `CONTROL_PLANE_SELECTED` only after authorized activation.
