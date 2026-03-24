import base64
import json
import gzip

# prepend serveproxy to a url if it exists so we can bypass cross origin blocks
def proxy_img(url: str) -> str:
    if url and isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
        return f"https://serveproxy.com/url?url={url}"
    return url

# recursively find and proxy image fields
def proxy_deep_images(obj):
    # these r the fields we look for inside dicts
    image_keys = {'coverImage', 'bannerImage', 'thumbnail', 'poster', 'image', 'large', 'medium', 'extraLarge'}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in image_keys and isinstance(value, str) and value.startswith("http"):
                obj[key] = proxy_img(value)
            elif isinstance(value, (dict, list)):
                proxy_deep_images(value)
    elif isinstance(obj, list):
        for item in obj:
            proxy_deep_images(item)
    return obj

# transform episode data without adding slug IDs
def inject_source_slugs(data: dict, anilist_id: int):
    providers = data.get("providers", {})
    for provider_name, provider_data in providers.items():
        if not isinstance(provider_data, dict):
            continue
        episodes = provider_data.get("episodes", {})
        if not isinstance(episodes, dict):
            if isinstance(episodes, list):
                provider_data["episodes"] = {"sub": episodes}
                episodes = provider_data["episodes"]
            else:
                continue
    return data

# decode base64 encoded text
def translate_id(encoded_id: str) -> str:
    try:
        # just handle base64 padding properly so it wont crash on decode
        decoded = base64.urlsafe_b64decode(encoded_id + '=' * (4 - len(encoded_id) % 4)).decode()
        if ':' in decoded:
            return decoded
        return encoded_id
    except Exception:
        return encoded_id

# go through standard json and decode all `id` strings
def deep_translate(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'id' and isinstance(value, str):
                obj[key] = translate_id(value)
            elif isinstance(value, (dict, list)):
                deep_translate(value)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                deep_translate(item)

# decode a base64 string compressed with gzip using pipe response logic
def decode_pipe_response(encoded_str: str) -> dict:
    try:
        encoded_str += '=' * (4 - len(encoded_str) % 4)
        compressed = base64.urlsafe_b64decode(encoded_str)
        return json.loads(gzip.decompress(compressed).decode('utf-8'))
    except Exception:
        # if reading fails throw an error
        raise ValueError("failed to decode pipe response")

# encode a dict back into base64 payload to send properly
def encode_pipe_request(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
