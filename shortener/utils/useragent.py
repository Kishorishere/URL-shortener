import user_agents


def parse_user_agent(ua_string: str) -> dict:
    if not ua_string:
        return {"browser": "", "os": "", "device_type": "desktop"}
    ua = user_agents.parse(ua_string)
    if ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    else:
        device_type = "desktop"
    return {
        "browser": ua.browser.family,
        "os": ua.os.family,
        "device_type": device_type,
    }
