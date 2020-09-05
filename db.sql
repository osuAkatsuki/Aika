create table aika_users
(
	discordid bigint(20) not null,
	guildid bigint(20) not null,
	xp int(11) default 0 not null,
	last_xp int(11) default 0 not null,
	strikes smallint(6) default 0 not null comment 'I guess tinyint could be too small? lol',
	muted_until int(11) default 0 not null,
	notes varchar(2048) null comment 'Probably enough space?',
	primary key (discordid, guildid)
);

create table aika_guilds
(
	guildid bigint(20) not null
		primary key,
	cmd_prefix varchar(8) default '!' not null,
	max_strikes smallint(6) default 3 not null,
	moderation tinyint(1) default 0 not null,
	constraint aika_guilds_guildid_uindex
		unique (guildid)
);

# For akatsuki-specific usage.
create table aika_akatsuki
(
	discordid bigint(20) not null
		primary key,
	osu_id int(11) null,
	constraint aika_akatsuki_osu_id_uindex
		unique (osu_id),
	constraint aika_akatsuki_aika_users_discordid_fk
		foreign key (discordid) references aika_users (discordid)
);

create table aika_faq
(
  id      int(11) primary key auto_increment,
  topic   varchar(32)   not null,
  title   varchar(128)  not null,
  content varchar(1024) not null,
  constraint aika_faq_content_uindex
    unique (content),
  constraint aika_faq_id_uindex
    unique (id),
  constraint aika_faq_title_uindex
    unique (title),
  constraint aika_faq_topic_uindex
    unique (topic)
);
