#!/usr/bin/env python3
import os
import json
import argparse
import subprocess
import locale
import re
from datetime import datetime

import tornado.ioloop
import tornado.web
import tornado.autoreload

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


def run_process(command):
	encoding = locale.getdefaultlocale()[1]
	with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
		return [line.decode(encoding) for line in  proc.stdout]


class Commit:
	line_pattern = re.compile('(.*) -- (.*) -- (.*)')

	def __init__(self, line=None, ref_hash=None, repo=None, user=None):
		if line is not None:
			self.parse_line(line)
		else:
			self.user = user
			self.repo = repo
			self.ref_hash = ref_hash

			commit_show = self.commit_text()
			self.parse_line(commit_show[0])

	def parse_line(self, line):
		search = Commit.line_pattern.search(line)
		self.time = datetime.strptime(search.group(1), '%Y-%m-%d %H:%M:%S %z')
		self.message = '"{}"'.format(search.group(2))
		self.ref_hash = search.group(3)

	@property
	def time_string(self):
		return self.time.strftime('%Y-%m-%d - %H:%M')

	def __str__(self):
		return '<Commit message:{} hash:{} time:{}>'.format(self.message, self.ref_hash, self.time)

	def commit_text(self):
		os.chdir(os.path.join(BASE_PATH, 'data', self.user, self.repo))
		commit_show = run_process(['git', 'show', self.ref_hash, '-U999999999', '--pretty=%ci -- %s -- %H'])
		os.chdir(BASE_PATH)
		return commit_show

	@property
	def diff(self):
		change_lines = []
		file_start_line = 0
		commit_text = self.commit_text()

		for index, line in enumerate(commit_text):
			if re.match('@@ .+ @@', line):
				file_start_line = index + 1

		print(commit_text)
		for line in commit_text[file_start_line:]:
			if not re.match('^[-+]$', line):
				line = line.replace('\n', '')
				line = line.replace('$NEWLINE', '</br>')
				change_word = re.search('^[-\\s+](.*)', line).group(1)

				if re.match('^\+', line):
					line = '<span class="changes addition">{}</span>'.format(change_word)
				elif re.match('^-', line):
					line = '<span class="changes deletion">{}</span>'.format(change_word)
				else:
					line = '<span class="changes normal">{}</span>'.format(change_word)

				change_lines.append(line)

		return '\n'.join(change_lines)

def commit(repo, message):
	os.chdir(os.path.join(BASE_PATH, repo))
	run_process(['git', 'add', 'data.txt'])
	run_process(['git', 'commit', '-m', message])
	os.chdir(BASE_PATH)


def load_json_file(filename):
	with open('json/{}'.format(filename), 'r') as jsonfile:
		return json.load(jsonfile)


class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.render('index.html')

class SingleCommitHandler(tornado.web.RequestHandler):
	def get(self, user, repo, commit_hash):
		if os.path.exists(os.path.join(BASE_PATH, 'data', user, repo, '.git')):
			c = Commit(ref_hash=commit_hash, user=user, repo=repo)
			self.render('commit.html', commit=c, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')


class CommitsHandler(tornado.web.RequestHandler):
	def get(self, user, repo):
		self.user = user
		self.repo = repo

		if os.path.exists(os.path.join(BASE_PATH, 'data', user, repo, '.git')):
			commits = self.commits()
			self.render('changes.html', commits=commits, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

	def commits(self):
		os.chdir(os.path.join(BASE_PATH, 'data', self.user, self.repo))
		commit_text = run_process(['git', 'log', '--all', '--pretty="%ci -- %s -- %H"'])

		os.chdir(BASE_PATH)

		commit_objs = []
		for line in commit_text:
			text = re.match('"([^"]+)"', line.split('\n')[0]).group(1)

			commit_objs.append(Commit(text))

		return commit_objs

class EditHandler(tornado.web.RequestHandler):
	def get(self, user, repo):
		if os.path.exists(os.path.join('data', user, repo, '.git')):
			try:
				with open(os.path.join('data', user, repo, 'data.txt')) as data_file:
					data = ''.join(data_file.readlines()).replace('\n', ' ').replace(' $NEWLINE ', '\n')
			except FileNotFoundError:
				data = ''
			self.render('repo.html', data=data, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

	def post(self, user, repo):
		data = self.get_argument('data').replace('\n', ' $NEWLINE ').replace(' ', '\n') + '\n'
		commit_message = self.get_argument('commit_message')
		repo_path = os.path.join('data', user, repo)
		data_path = os.path.join(repo_path, 'data.txt')

		if os.path.exists(os.path.join(repo_path, '.git')):
			with open(data_path, 'w') as data_file:
				data_file.writelines(data)
			commit(repo_path, commit_message)
			self.render('repo.html', data=data, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')


class UserListHandler(tornado.web.RequestHandler):
	def get(self):
		users = os.listdir(os.path.join('data'))
		self.render('users.html', users=users)


class UserHandler(tornado.web.RequestHandler):
	def get(self, user):
		if os.path.exists(os.path.join('data', user)):
			repos = os.listdir(os.path.join('data', user))
			self.render('user.html', repos=repos, user=user)
		else:
			self.finish('REPO NOT FOUND')

	def post(self, user):
		path = os.path.join(BASE_PATH, 'data', user)
		if not os.path.exists(path):
			os.mkdir(path)
			UserListHandler.get(self)
		else:
			self.finish('USER {} HAS EXISTING ACCOUNT'.format(user))


class RepoHandler(tornado.web.RequestHandler):
	def post(self, user, repo):
		path = os.path.join(BASE_PATH, 'data', user, repo)

		if os.path.exists(os.path.join(BASE_PATH, 'data', user):
			self.finish('USER {} DOES NOT EXIST')

		if not os.path.exists(path):
			os.mkdir(path)
			os.chdir(path)
			run_process(['git', 'init'])
			os.chdir(BASE_PATH)
			EditHandler.get(self, user, repo)
		else:
			self.finish('PROJECT {}/{} EXISTS'.format(user, repo))

handlers = [
	(r'/', UserListHandler),
	(r'/([^/]+)/([^/]+)/edit', EditHandler),
	(r'/([^/]+)/([^/]+)/change', CommitsHandler),
	(r'/([^/]+)/([^/]+)/change/([^/]+)', SingleCommitHandler),
	(r'/([^/]+)', UserHandler),
	(r'/([^/]+)/([^/]+)', RepoHandler),
]

settings = {
	'debug': True,
	'static_path': os.path.join(BASE_PATH, 'static'),
	'template_path': os.path.join(BASE_PATH, 'templates')
}

application = tornado.web.Application(handlers, **settings)


def parse_args():
	parser = argparse.ArgumentParser(
		description='Server application for the Historian app',
		prog='server.py'
	)

	parser.add_argument(
		'-p',
		'--port',
		metavar='PORT',
		type=int,
		help='The port that this instance of the server should listen on'
	)

	args = parser.parse_args()

	return args

if __name__ == '__main__':
	args = parse_args()

	tornado.autoreload.start()

	application.listen(args.port)
	tornado.ioloop.IOLoop.instance().start()
