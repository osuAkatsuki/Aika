create table aika_users
(
	discordid bigint not null,
	guildid bigint not null,
	xp int default 0 not null,
	last_xp int default 0 not null,
	strikes smallint(6) default 0 not null comment 'I guess tinyint could be too small? lol',
	notes varchar(2048) null comment 'Probably enough space?',
	primary key (discordid, guildid)
);

create table aika_faq
(
  id      int primary key auto_increment,
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

# For akatsuki-specific usage.
create table aika_akatsuki
(
	discordid bigint not null
		primary key,
	osu_id int null,
	constraint aika_akatsuki_osu_id_uindex
		unique (osu_id),
	constraint aika_akatsuki_aika_users_discordid_fk
		foreign key (discordid) references aika_users (discordid)
);
