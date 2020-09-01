Aika
====

As of the 27th of June, Aika is now a public bot!
This means you can [invite them to your server](https://discord.com/api/oauth2/authorize?client_id=702310727515504710&permissions=0&scope=bot), if you'd like. :)

In the past I've written some Discord bots, which have iteratively improved my code for every rewrite I undergo; and with all the free time from quarantine, I thought I'd give Aika another go, this time with a bit more planning..

So far, the bot has come a long way; it's [far](https://github.com/cmyui/Aika_old) better than my previous attempts, and it feels like my improvement rate is increasing exponentially (quarantine gives me pretty much infinite time to work on programming).. Maybe this won't end up half bad?

Commands

========

```md
Mandatory = <>
Optional = ()

Using commands like !u, !rc, !top, etc. with
no parameters will simply retrieve your own.
(assuming your akatsuki account is linked)

# General commands
!<u/user/profile> (@mention) # display your (or target's) user profile.
!<levelreq/lvreq> <level> # show the xp required for a specific level
!<lb/xplb/leaderboard> # show the current guild's xp leaderboards.
!<lv/level> # may be removed since !u exists
!<uptime> # shows Aika's time online
!<prune> <count [max 1000]> # prune messages from a channel (up to 1k)

# Akatsuki commands
!<top> (-rx) (-gm 0/1) (@mention/akatsuki username) # shows your (or target's) best 3 plays on akatsuki
!<rc/recent> (@mention/akatsuki username) # shows your (or target's) most recent score on akatsuki
!<link/linkosu> # allows you to link your akatsuki account to discord

# Akatsuki-only commands (only available in akatsuki's discord)
!<faq> (name/id) # get FAQ topics
```

Requirements
------------

- Python >= 3.8
- MySQL
