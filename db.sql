create table aika_users
(
  id               bigint primary key not null,
  xp_cooldown      int default 0      not null,
  deleted_messages int default 0      not null,
  osu_id           bigint             null
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

create table aika_xp
(
	discord_id bigint not null,
	guild_id   bigint not null,
	xp         int    not null,
	primary key (discord_id, guild_id)
);
