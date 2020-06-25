create table aika_users
(
  id               bigint        not null,
  xp               int default 0 not null,
  xp_cooldown      int default 0 not null,
  deleted_messages int default 0 not null,
  osu_id           bigint        null,
  constraint aika_users_id_uindex
    unique (id)
);

alter table aika_users
  add primary key (id);


create table aika_faq
(
  id      int auto_increment,
  topic   varchar(32)   not null,
  title   varchar(55)   not null,
  content varchar(2000) not null,
  constraint aika_faq_content_uindex
    unique (content),
  constraint aika_faq_id_uindex
    unique (id),
  constraint aika_faq_title_uindex
    unique (title),
  constraint aika_faq_topic_uindex
    unique (topic)
);

alter table aika_faq
  add primary key (id);
