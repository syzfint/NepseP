from nepse_client import NepseClient
import json

c = NepseClient()
c.setTLSVerification(False)
ep = c.api_end_points['floor_sheet']
url = f"{ep}?size=50&sort=contractId,desc"
sheet = c.requestPOSTAPI(url=url, payload_generator=c.getPOSTPayloadIDForFloorSheet)
print("Type of sheet:", type(sheet))
if isinstance(sheet, dict):
    print("Keys:", list(sheet.keys()))
    if "floorsheets" in sheet:
        print("floorsheets type:", type(sheet["floorsheets"]))
        if isinstance(sheet["floorsheets"], list):
            print("floorsheets list length:", len(sheet["floorsheets"]))
            if sheet["floorsheets"]:
                print("First trade:", sheet["floorsheets"][0])
        elif isinstance(sheet["floorsheets"], dict):
            print("floorsheets dict keys:", list(sheet["floorsheets"].keys()))
elif isinstance(sheet, list):
    print("List length:", len(sheet))
    if sheet:
        print("First item:", sheet[0])
