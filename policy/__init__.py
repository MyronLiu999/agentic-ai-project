"""The autonomy policy (Milestone 2, Part 2). The model never sees anything in this package: it is
never put in a prompt or a tool definition. hook.py (myron) answers every tool call before it runs;
flags.py holds the operator's stops and rules.py the limits the operator stated, both parsed by code."""
