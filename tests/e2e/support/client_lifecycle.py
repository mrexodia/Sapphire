"""Normal retirement of an owned headless witness, not offline reset authority."""


def retire_witness(bot):
    # Bot.logout's default waits only for acknowledgement. A passing manual
    # lane must allow the server to complete the witness session before teardown.
    # Do not catch/convert failures or retry an uncertain logout/removal.
    bot.logout(wait_server_close=True)
    bot.close()
    return {"bot": bot.name, "server_close_observed": True, "native_bot_removed": True,
            "scope": "normal-witness-session-retirement-not-offline-exclusion"}
