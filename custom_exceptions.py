from discord.app_commands.errors import CheckFailure


class UserVoiceChannelError(CheckFailure):
    pass


class BotVoiceChannelError(CheckFailure):
    pass


class DifferentVoiceChannelsError(CheckFailure):
    pass
