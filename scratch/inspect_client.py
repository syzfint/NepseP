import inspect
from nepse_client import NepseClient

c = NepseClient()
print("getPOSTPayloadIDForFloorSheet:")
print(inspect.getsource(c.getPOSTPayloadIDForFloorSheet))

print("\nrequestPOSTAPI:")
print(inspect.getsource(c.requestPOSTAPI))
