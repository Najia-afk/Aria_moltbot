#!/usr/bin/env python3
"""Test WebSocket session management against clawdbot gateway."""
import aiohttp
import asyncio
import json
import os


async def test_connect_and_list():
    token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")
    port = os.environ.get("OPENCLAW_GATEWAY_PORT", "18789")
    url = f"ws://localhost:{port}"

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, origin=f"http://localhost:{port}") as ws:
            # 1) Send initial connect
            await ws.send_json({
                "type": "req", "id": "c1",
                "method": "connect",
                "params": {
                    "minProtocol": 3, "maxProtocol": 3,
                    "client": {"id": "openclaw-control-ui", "version": "1.0", "platform": "python", "mode": "webchat"},
                    "role": "operator",
                    "scopes": ["operator.admin"],
                    "auth": {"token": token},
                }
            })

            # 2) Read challenge
            msg = await asyncio.wait_for(ws.receive(), timeout=5)
            data = json.loads(msg.data)
            print(f"1st: type={data.get('type')} event={data.get('event','')}")

            if data.get("event") == "connect.challenge":
                nonce = data["payload"]["nonce"]
                print(f"    nonce={nonce}")

                # 3) Re-send connect (same payload, gateway now has nonce)
                await ws.send_json({
                    "type": "req", "id": "c2",
                    "method": "connect",
                    "params": {
                        "minProtocol": 3, "maxProtocol": 3,
                        "client": {"id": "openclaw-control-ui", "version": "1.0", "platform": "python", "mode": "webchat"},
                        "role": "operator",
                        "scopes": ["operator.admin"],
                        "auth": {"token": token},
                    }
                })

                # 4) Read response
                msg2 = await asyncio.wait_for(ws.receive(), timeout=5)
                data2 = json.loads(msg2.data)
                print(f"2nd: type={data2.get('type')} ok={data2.get('ok','')} err={data2.get('error','')}")

                if data2.get("ok"):
                    print("AUTH SUCCESS - trying sessions.list")
                    await ws.send_json({
                        "type": "req", "id": "sl1",
                        "method": "sessions.list",
                        "params": {"includeGlobal": True, "limit": 5}
                    })
                    msg3 = await asyncio.wait_for(ws.receive(), timeout=5)
                    data3 = json.loads(msg3.data)
                    print(f"sessions.list: ok={data3.get('ok','')} type={data3.get('type','')}")
                    if data3.get("ok") and data3.get("payload"):
                        sessions = data3["payload"].get("sessions", data3["payload"])
                        if isinstance(sessions, list):
                            print(f"  count={len(sessions)}")
                            for s in sessions[:3]:
                                print(f"  key={s.get('key','')} sid={s.get('sessionId','')[:12]}")
                        else:
                            print(f"  payload keys: {list(data3['payload'].keys())[:10]}")
                    else:
                        print(f"  raw: {json.dumps(data3)[:300]}")


if __name__ == "__main__":
    asyncio.run(test_connect_and_list())
