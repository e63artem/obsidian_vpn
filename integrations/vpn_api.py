from pathlib import Path

import aiohttp


BASE_URL = 'http://91.196.34.46:51821'


async def __get_session():
    url = 'http://91.196.34.46:51821/api/session'
    payload = {
        'password': 'hr67jwH6S365'
    }
    headers = {
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            session_cookie = response.headers.get('Set-Cookie').split(';')[0]
            return session_cookie


async def create_vpn_user(user_id: int):
    client_id = await get_client_id(str(user_id))
    if client_id:
        return client_id
    else:
        s_id = await __get_session()
        url = f"{BASE_URL}/api/wireguard/client"
        payload = {"name": f"{user_id}"}
        headers = {
            "Content-Type": "application/json",
            "Cookie": f'{s_id}'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                # print(response)
                result = await response.json()
                return result


async def __get_clients():
    url = f"{BASE_URL}/api/wireguard/client"
    async with aiohttp.ClientSession() as session:
        s_id = await __get_session()
        headers = {
            "Content-Type": "application/json",
            "Cookie": f'{s_id}'
        }
        async with session.get(url, headers=headers) as resp:
            result = await resp.json()
            return result


async def get_client_id(name: str):
    clients = await __get_clients()
    client_id = None
    for c in clients:
        if c['name'] == name:
            client_id = c['id']
            break
    return client_id


async def download_config(name, cid: str):
    url = f"{BASE_URL}/api/wireguard/client/{cid}/configuration"
    async with aiohttp.ClientSession() as session:
        s_id = await __get_session()
        headers = {
            "Content-Type": "application/json",
            "Cookie": f'{s_id}'
        }
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                config_data = await resp.read()
                # Путь на директорию выше и в папку downloads/
                downloads_dir = Path(__file__).resolve().parent.parent / "downloads"
                downloads_dir.mkdir(parents=True, exist_ok=True)  # ← создаёт папку, если её нет
                filename = downloads_dir / f"{name}.conf"
                with open(filename, "wb") as f:
                    f.write(config_data)
                print(f"✅ Конфиг сохранён в файл {filename}")
                return filename
            else:
                text = await resp.text()
                print(f"❌ Ошибка скачивания конфига: {resp.status}\n{text}")


async def disable(uid: int):
    sid = await __get_session()
    cid = await get_client_id(str(uid))
    url = f"{BASE_URL}/api/wireguard/client/{cid}/disable"
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Cookie": f'{sid}'
        }
        async with session.post(url, headers=headers) as response:
            result = await response.json()
            return result


async def enable(uid: int):
    sid = await __get_session()
    cid = await get_client_id(str(uid))
    url = f"{BASE_URL}/api/wireguard/client/{cid}/enable"
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Cookie": f'{sid}'
        }
        async with session.post(url, headers=headers) as response:
            result = await response.json()
            return result
