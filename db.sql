CREATE TABLE `aika_xp` (
  `user` bigint(20) NOT NULL,
  `xp` int(11) DEFAULT '0',
  `last_claimed` int(10) NOT NULL,
  PRIMARY KEY (`user`),
  UNIQUE KEY `aika_xp_user_uindex` (`user`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

CREATE TABLE `aika_faq` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `topic` varchar(32) NOT NULL,
  `title` varchar(128) NOT NULL,
  `content` varchar(1024) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `aika_faq_content_uindex` (`content`),
  UNIQUE KEY `aika_faq_title_uindex` (`title`),
  UNIQUE KEY `aika_faq_topic_uindex` (`topic`),
  UNIQUE KEY `aika_faq_id_uindex` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
