# Aika - osu!Akatsuki support & general moderation in modern python

As of the 27th of June, Aika is now a public bot!
This means you can [invite them to your server](https://discord.com/api/oauth2/authorize?client_id=702310727515504710&permissions=0&scope=bot), if you'd like. :)

In the past I've written some Discord bots, which have iteratively improved my code for every rewrite they undergo; and with all the free time from quarantine, I thought I'd give Aika another go, this time with a bit more planning and experience..

So far, the bot has come a long way; it's [uncomparable](https://github.com/cmyui/Aika_old) to my previous attempts, and my improvement rate  (quarantine gives me pretty much infinite time to work on programming)..

## Command Reference

```md
Mandatory = <> | Optional = ()

Using commands like !u, !rc, !top, etc. with
no parameters will simply retrieve your own.
(assuming you've used !link with your account)

# General commands
!user (@mentions ...) # display your (or @mention's) user profile
!lvreq <level> # show the xp required for a specific level
!leaderboard # show the current guild's xp leaderboards
!level # may be removed since !u exists
!uptime # shows Aika's time online
!prune <count> # prune messages from a channel (up to 1k)

# Guild commands
!setprefix (prefix) # set Aika's prefix within the guild
!moderation <on/off> # toggle moderation commands within the guild

# Moderation commands (must be enabled with `!moderation on`)
!strike <@mentions ...> # add a strike to user(s)
!mute <duration>(period) <@mentions ...> # mute a specified user for a given time, period is (s/m/h/d/w)

# Akatsuki commands
!top (-gm #) (-rx) (username/mentions ...) # shows your (or target's) best 3 plays on akatsuki
!recent (-gm #) (-rx) (username/mentions ...) # shows your (or target's) most recent score on akatsuki
!link # allows you to link your akatsuki account to discord

# Akatsuki-only commands (only available in Akatsuki's discord)
!faq (topic) # get akatsuki-related help (frequently asked questions)
```

## Requirements

- python3.8 & mysql
