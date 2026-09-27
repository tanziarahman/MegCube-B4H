"""Fake B4H responses for tests. Shapes are guesses of the real box format."""
MATCHED, STRANGER = "face_comparison_successful", "face_comparison_failed"


def _row(i: int, minor: str) -> dict:
    matched = minor == MATCHED
    return {"alarm_info": {
        "global_info": {"data_uuid": f"{minor[:4]}-{i}", "device_id": "SN1", "time_ms": str(1790224000000 + i * 60000)},
        "additional": {"alarm_major": "face_basic_business", "alarm_minor": minor},
        "channel_info": {"channel_id": "1", "channel_name": "Hikvision"},
        "face_info": {"track_id": 5100 + i, "living_score": 0,
                      "compare_result": {"score": 79.0 if matched else 41.0, "person_name": "Tanzia" if matched else "",
                                         "groups": [{"group_name": "Ticon"}, {"group_name": "Default Group"}] if matched else []}},
        "images": [
            {"image_type": "face", "image_data_format": 2, "image_data": f"./snap/face_{i}.jpg"},
            {"image_type": "background", "image_data_format": 2, "image_data": f"./snap/bg_{i}.jpg"},
        ],
    }}


class FakeBox:
    def __init__(self, matched=22, stranger=5):
        self.n = {MATCHED: matched, STRANGER: stranger}
        self.calls: list = []

    async def login(self): ...
    async def close(self): ...

    async def call(self, method, path, body=None, params=None):
        self.calls.append((method, path, body))
        if path == "/device_alarm/alarm_history":
            minor = body["query_condition"]["alarm_type"][0]["minor_type"][0]
            rows = [_row(i, minor) for i in range(self.n[minor])][::-1]     # newest first
            return {"total": len(rows), "alarm_list": rows[body["offset"]:body["offset"] + body["size"]]}
        if path == "/device_access/device_config":
            return {"list": [{"device_id": "1", "device_name": "Hikvision"}]}
        if path == "/device_access/device_state":
            return {"list": [{"device_id": "1", "status": "online"}]}
        if path == "/face_manager/groups/query":
            return {"groups": [{"group_id": "1", "group_name": "Default Group"}, {"group_id": "2", "group_name": "Ticon"}]}
        return {}

    async def get_bytes(self, path, params=None):
        return b"\xff\xd8jpeg", "image/jpeg"
