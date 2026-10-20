import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('WEB_WORKERS', '2'))
worker_class = 'gthread'
threads = 2
timeout = 60
graceful_timeout = 30
keepalive = 5
worker_tmp_dir = '/tmp'
accesslog = '-'
errorlog = '-'
capture_output = True
# Django handles the one scheme header overwritten by our private frontend.
# Never let request headers override SCRIPT_NAME or PATH_INFO in Gunicorn.
forwarded_allow_ips = ''
forwarder_headers = ''
secure_scheme_headers = {}
