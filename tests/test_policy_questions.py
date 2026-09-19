from fastapi.testclient import TestClient


def test_source_policy_questions_are_answered_in_chinese(tmp_path):
    from app.main import create_app

    questions = [
        ("摩托车保险有哪些保障？", "motorcycle_policy.md"),
        ("综合汽车保单是否承保车辆盗窃？", "comprehensive_auto_policy.md"),
        ("商业汽车责任险限额怎么规定？", "COMM-AUTO-001"),
        ("高价值车辆的改装和售后配件是否有保障？", "HV-AUTO-001"),
        ("责任险不承保哪些损失？", "LIAB-AUTO-001"),
    ]
    with TestClient(create_app(db_path=tmp_path / "claims.sqlite3")) as client:
        for question, source in questions:
            response = client.post("/v1/chat", json={"messages": [{"role": "user", "content": question}]})
            assert response.status_code == 200
            payload = response.json()
            assert any("\u4e00" <= char <= "\u9fff" for char in payload["content"])
            assert source in payload["content"]
