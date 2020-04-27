CREATE TABLE `aika_users` (
  `id` bigint(20) NOT NULL,
  `xp` int(11) NOT NULL DEFAULT '0',
  `xp_cooldown` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `aika_users_id_uindex` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE `aika_faq` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `topic` varchar(32) NOT NULL,
  `title` varchar(128) NOT NULL,
  `content` varchar(2000) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `aika_faq_content_uindex` (`content`),
  UNIQUE KEY `aika_faq_title_uindex` (`title`),
  UNIQUE KEY `aika_faq_topic_uindex` (`topic`),
  UNIQUE KEY `aika_faq_id_uindex` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
