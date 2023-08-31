NO_SEQ = 0

NO_PTS = 0

# https://core.telegram.org/method/updates.getChannelDifference
BOT_CHANNEL_DIFF_LIMIT = 100000
USER_CHANNEL_DIFF_LIMIT = 100

POSSIBLE_GAP_TIMEOUT = 0.5

# https://core.telegram.org/api/updates
NO_UPDATES_TIMEOUT = 15 * 60

ACCOUNT_WIDE = "ACCOUNT"
SECRET_CHATS = "SECRET"


class Gap(ValueError):
    pass
