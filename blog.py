"""A simple webapp2 server."""

import webapp2
import string
import cgi
import re
import jinja2
import os
import hmac
import json
from google.appengine.ext import db
from time import sleep
import time
from google.appengine.api import memcache
from google.appengine.api import mail
import logging
from utils import *

APP_ID = "tenzingsalgs"

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir)
                               ,autoescape = True)

update = False

class Posts(db.Model):
  subject = db.StringProperty(required = True)
  content = db.TextProperty(required = True)
  created = db.DateProperty(auto_now_add = True)

class Comments(db.Model):
  post_id = db.IntegerProperty(required = True)
  content = db.TextProperty(required = True)
  username = db.StringProperty(required = True)
  created = db.DateProperty(auto_now_add = True)
  useremailhash = db.StringProperty()

class Users(db.Model):
  username = db.StringProperty(required = True)
  passwordhash = db.StringProperty(required = True)
  salt = db.StringProperty(required = True)
  email = db.StringProperty()
  emailhash = db.StringProperty()

class Handler(webapp2.RequestHandler):
  def write(self, *a, **kw):
    self.response.out.write(*a, **kw)

  def render_str(self, template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

  def render(self, template, **kw):
    self.write(self.render_str(template, **kw))

class MainPage(Handler):
  def render_front(self):
    global update
    key = 'front'
    posts = memcache.get(key)
    if not posts or update:
      update = False
      posts = db.GqlQuery("select * from Posts order by created desc")
      memcache.set(key, posts)
    post_comments = []
    for p in posts:
      post_id = str(p.key().id())
      comments = db.GqlQuery("select * from Comments where post_id="+ post_id)
      post_comments.append((p, comments))
    uname = self.request.cookies.get("username")
    username = emailhash = ""
    if uname:
      username = uname.split("|")[0]
      user = db.GqlQuery("select * from Users where username='" + username + "'").get()
      emailhash = user.emailhash
    self.render("blog_front.html", post_comments = post_comments, 
                                   username = username, emailhash=emailhash)

  def get(self):
    self.render_front()

class NewPost(Handler):
  def render_newpost(self, subject="", content="", error=""):
    self.render("blog_newpost.html", subject=subject, content=content,
                                     error=error)

  def get(self):
    self.render_newpost()

  def post(self):
    global update
    subject = self.request.get("subject")
    content = self.request.get("content")
    if subject and content:
      p = Posts(subject = subject, content = content)
      p.put()
      update = True
      sleep(1)
      self.redirect("/" + str(p.key().id()))
    else:
      error = "subject and content please!"
      self.render_newpost(subject, content, error)

class PLink(Handler):
  def get(self, post_id):
    post = memcache.get(post_id)
    if not post:
      post = Posts.get_by_id(int(post_id))
      memcache.set(post_id, post)
    self.render("blog_post.html", post = post)

  def post(self, post_id):
    username = "Anonymous"
    useremailhash = ""
    uname = self.request.cookies.get("username")
    if uname:
      username = uname.split("|")[0]
      user = db.GqlQuery("select * from Users where username='" + username + "'").get()
      useremailhash = user.emailhash
    content = self.request.get("comment-content")

    c = Comments(post_id = int(post_id), content = content, username = username, useremailhash = useremailhash)
    c.put()
    sleep(1)
    self.redirect("/")

class Signup(Handler): 
  def render_signup(self, username = "", email = "", username_error = "",
                    email_error = "", password_error = "", match_error = "",
                    unique_error = ""):
    self.render("blog_signup.html", username=username, email=email, 
                 username_error=username_error, email_error=email_error,
                 password_error=password_error, verify_error=match_error,
                 unique_error = unique_error)

  def get(self):
    self.render_signup()

  def post(self):
    username = self.request.get('username')
    password = self.request.get('password')
    verify = self.request.get('verify')
    email = self.request.get('email')
    u_error = p_error = v_error = e_error = ""
    if not valid_username(username):
      u_error = "That's not a valid username."
    if not valid_password(password):
      p_error = "That wasn't a valid password."
    elif password != verify:
      v_error = "Your passwords didn't match."
    if email and not valid_email(email):
      e_error = "That's not a valid email."
    if u_error or p_error or v_error or e_error:
      self.render_signup(username, email, u_error, e_error, p_error, v_error)
    else:
      user = db.GqlQuery("select * from Users where username='" + username + "'").get()
      if user:
        self.render_signup(username, email, unique_error = "Username already taken.")
      else:
        self.response.headers.add_header('Set-Cookie', 'username=' +
                                          str(make_secure_val(username)) + '; Path=/')
        emailhash = ""
        if email:
          # Send the user a confirmation email
          subject = "Welcome to Tenzing's Algorithms Blog!"
          body = "Thanks for registering on Tenzing's Algorithms Blog!"
          mail.send_mail("welcome@" + APP_ID + ".appspotmail.com", email, subject, body)
          # Hash the email for gravatar purposes
          emailhash = gravatar_hash_email(email)
        passwordhash, salt = hash_password(password)
        u = Users(username = username, passwordhash = passwordhash, 
                  email = email, emailhash = emailhash, salt = salt)
        u.put()
        self.redirect("/welcome")

class Login(Handler):
  def render_login(self, error = ""):
    self.render("blog_login.html", error=error)
  
  def get(self):
    self.render_login()

  def post(self):
    username = self.request.get('username')
    user = db.GqlQuery("select * from Users where username='" + 
                          str(username) + "'").get()
    if not user:
      self.render_login(error = "Invalid login")
    else:
      passwordhash, salt = hash_password(self.request.get('password'), user.salt)
      if passwordhash != user.passwordhash:
        self.render_login(error = "Invalid login")
      else:
        self.response.headers.add_header('Set-Cookie', 'username=' +
                                        str(make_secure_val(username)) + '; Path=/')
        self.redirect("/welcome")

class Welcome(Handler):
  def render_welcome(self):
    username = self.request.cookies.get('username')
    if not username:
      self.redirect("/signup")
    else:
      s, h = username.split("|")
      if check_secure_val(s, h):
        self.render("blog_welcome.html", username=s)
      else:
        self.redirect("/signup")

  def get(self):
    self.render_welcome()

class Logout(Handler):
  def get(self):
    self.response.set_cookie('username', '')
    self.response.set_cookie('password', '')
    self.redirect("/")

class JsonFront(webapp2.RequestHandler):
  def get(self):
    posts = db.GqlQuery("select * from Posts order by created desc")
    self.response.headers["Content-Type"] = "application/json"
    self.response.out.write(json.dumps([{"content":p.content, 
                                         "subject":p.subject} for p in posts]))

class JsonPLink(webapp2.RequestHandler):
  def get(self, post_id):
    posts = db.GqlQuery("select * from Posts where post_id=" + str(post_id))
    post = posts.get()
    self.response.headers["Content-Type"] = "application/json"
    self.response.out.write(json.dumps({"content": post.content, 
                                        "subject": post.subject}))

class Flush(webapp2.RequestHandler):
  def get(self):
    memcache.flush_all()
    self.redirect('/')

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/newpost', NewPost),
                               (r'/(\d+)', PLink),
                               ('/signup', Signup),
                               ('/login', Login),
                               ('/logout', Logout),
                               ('/welcome', Welcome),
                               ('/.json', JsonFront),
                               ('/(\d+).json', JsonPLink),
                               ('/flush', Flush)], debug=True)
