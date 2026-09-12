import re

with open("/Users/avinavkumar0045/Desktop/AgentOps/src/agent/api.py", "r") as f:
    code = f.read()

code = code.replace("except Exception as e:", "except Exception as e:\n            import traceback\n            traceback.print_exc()\n")

with open("/Users/avinavkumar0045/Desktop/AgentOps/src/agent/api.py", "w") as f:
    f.write(code)
