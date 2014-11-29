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


class CommitsHandler(tornado.web.RequestHandler):
	def get(self, user, repo):
		self.user = user
		self.repo = repo

		if os.path.exists(os.path.join(BASE_PATH, 'data', user, repo, 'data.txt')):
			commits = self.commits()
			self.render('changes.html', commits=commits, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

	def commits(self):
		os.chdir(os.path.join(BASE_PATH, 'data', self.user, self.repo))
		commit_text = run_process(['git', 'log', '--all', '--pretty="%ci -- %s"'])

		os.chdir(BASE_PATH)

		message = re.compile('(.*) -- (.*)')

		commit_objs = []
		for commit in commit_text:
			line = re.match('"([^"]+)"', commit.split('\n')[0]).group(1)
			commit_time = datetime.strptime(message.search(line).group(1), '%Y-%m-%d %H:%M:%S %z')
			commit_message = '"{}"'.format(message.search(line).group(2))
			time_string = commit_time.strftime('%Y-%m-%d - %H:%M')

			commit_objs.append((commit_message, time_string))

		return commit_objs

class EditHandler(tornado.web.RequestHandler):
	def get(self, user, repo):
		if os.path.exists(os.path.join('data', user, repo, 'data.txt')):
			with open(os.path.join('data', user, repo, 'data.txt')) as data_file:
				data = ''.join(data_file.readlines()).replace('\n', ' ').replace(' $NEWLINE ', '\n')
			self.render('repo.html', data=data, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

	def post(self, user, repo):
		data = self.get_argument('data').replace('\n', ' $NEWLINE ').replace(' ', '\n')
		commit_message = self.get_argument('commit_message')
		repo_path = os.path.join('data', user, repo)
		data_path = os.path.join(repo_path, 'data.txt')

		if os.path.exists(data_path):
			with open(data_path, 'w') as data_file:
				data_file.writelines(data)
			commit(repo_path, commit_message)
			self.render('repo.html', data=data, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

handlers = [
	(r'/', MainHandler),
	(r'/([^/]+)/([^/]+)/edit', EditHandler),
	(r'/([^/]+)/([^/]+)/change', CommitsHandler),
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
