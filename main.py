import json
import requests
import websocket
import time
import csv
import os


def main():
    server_id, channel_id, token = get_user_input()

    if not validate_token(token):
        print("[INVALID] Token.")
        return

    print(f"Scraping in {server_id} with {token}")
    members = scrape_members(token, server_id, channel_id)
    print(f"Total Scraped: {len(members)} unique members.")
    print(f"Scraped IDs saved to CSV.")


def get_user_input():
    server_id = input("Enter Server ID: ")
    channel_id = input("Enter Channel ID: ")
    token = input("Enter Token: ")
    return server_id, channel_id, token


def validate_token(token):
    url = "https://discord.com/api/v9/users/@me/affinities/guilds"
    headers = {
        "authorization": token,
        "user-agent": "Mozilla/5.0",
    }
    response = requests.get(url, headers=headers)
    return response.status_code == 200


def scrape_members(token, server_id, channel_id):
    ws = connect_to_websocket()

    csv_filename = create_csv_if_not_exists(server_id)
    scraped_users = set()  # 重複を防ぐためにセットを使用
    batch_size = 25
    start = 0
    retries = 5

    while True:
        try:
            message = json.loads(ws.recv())
            log_message(f"Received message: {message}")

            if message.get("t") == "READY_SUPPLEMENTAL":
                request_member_list(ws, server_id, channel_id, start, batch_size - 1)
            elif message.get("t") == "GUILD_MEMBER_LIST_UPDATE":
                scraped_users, has_more_data = process_member_list(message, csv_filename, scraped_users, batch_size)
                if has_more_data:
                    start += batch_size
                    request_member_list(ws, server_id, channel_id, start, start + batch_size - 1)
                else:
                    break
        except Exception as e:
            if retries > 0:
                retries -= 1
                log_message(f"Error: {e}. Retrying... ({5 - retries}/5)")
                time.sleep(3)
            else:
                log_message(f"Failed after 5 retries. Error: {e}")
                break

    ws.close()
    return scraped_users


def connect_to_websocket():
    ws_url = "wss://gateway.discord.gg/?v=10&encoding=json"
    ws = websocket.WebSocket()
    ws.connect(ws_url)
    return ws


def create_csv_if_not_exists(server_id):
    """CSVファイルが存在しない場合は作成する"""
    if not os.path.exists(csv_filename):
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["User ID"])
    return csv_filename


def process_member_list(message, csv_filename, scraped_users, batch_size):
    items = message["d"].get("ops", [])
    has_more_data = False

    for item in items:
        if "items" in item:
            for member in item["items"]:
                if "member" in member:
                    user_id = member["member"]["user"]["id"]
                    if user_id not in scraped_users:  # 重複を防ぐ
                        scraped_users.add(user_id)
                        save_to_csv(csv_filename, user_id)
            if len(item["items"]) == batch_size:
                has_more_data = True 

    return scraped_users, has_more_data


def request_member_list(ws, server_id, channel_id, start, end):
    send_data = {
        "op": 14,
        "d": {
            "guild_id": server_id,
            "typing": True,
            "activities": True,
            "threads": True,
            "channels": {
                channel_id: [[start, end]]
            }
        }
    }
    ws.send(json.dumps(send_data))
    time.sleep(3)


def save_to_csv(csv_filename, user_id):
    with open(csv_filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([user_id])


def log_message(message):
    print(message)


if __name__ == "__main__":
    main()
