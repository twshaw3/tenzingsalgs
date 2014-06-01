import hmac
import re
import hashlib
import os
import binascii

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASSWORD_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"^[\S]+@[\S+]+\.[\S]+$")

SECRET = "Richard of York Gave Battle in Vain"

def hash_password(password, salt = ""):
  if not salt:
    salt = binascii.b2a_hex(os.urandom(32))
  return (hashlib.sha256(password + salt + SECRET).hexdigest(), salt)

def hash_str(s):
  return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
  return "%s|%s" % (s, hash_str(s))

def check_secure_val(s, h):
  return hash_str(s) == h

def valid_username(username):
  return USER_RE.match(username)

def valid_password(password):
  return PASSWORD_RE.match(password)

def valid_email(email):
  return EMAIL_RE.match(email)

def gravatar_hash_email(email):
  email = email.strip().lower()
  return hashlib.md5(email).hexdigest()
