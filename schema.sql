drop table if exists users;
drop table if exists tweets;
create table users (
  id integer primary key autoincrement,
  username text not null,
  username_lower text not null,
  password text not null,
  admin integer
);
create table tweets (
  id integer primary key autoincrement,
  text text not null,
  user_id text,
  time integer
);