from nepse_client import NepseClient

c = NepseClient()
c.setTLSVerification(False)
c.token_manager.update()

try:
    pvh = c.getPriceVolumeHistory()
    print("SUCCESS getPriceVolumeHistory! Type:", type(pvh))
    if isinstance(pvh, dict):
        print("Keys:", list(pvh.keys()))
        if "content" in pvh:
            print("Content len:", len(pvh["content"]))
            if len(pvh["content"]) > 0:
                print("First record:", pvh["content"][0])
except Exception as e:
    print("getPriceVolumeHistory error:", e)

try:
    # Test specific page or small size of floorsheet
    url = f"{c.api_end_points['floor_sheet']}?size=50&sort=contractId,desc"
    sheet = c.requestPOSTAPI(url=url, payload_generator=c.getPOSTPayloadIDForFloorSheet)
    print("FloorSheet raw type:", type(sheet))
    if isinstance(sheet, dict):
        print("Sheet keys:", list(sheet.keys()))
        if "floorsheets" in sheet:
            print("floorsheets type:", type(sheet["floorsheets"]))
            if isinstance(sheet["floorsheets"], dict):
                print("floorsheets keys:", list(sheet["floorsheets"].keys()))
                content = sheet["floorsheets"].get("content", [])
                print("floorsheets content len:", len(content))
                if content:
                    print("Sample trade:", content[0])
except Exception as e:
    print("FloorSheet error:", e)
