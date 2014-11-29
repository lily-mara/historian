#!/usr/bin/env python3
import os
import json
import argparse
import subprocess

import tornado.ioloop
import tornado.web
import tornado.autoreload

BASE_PATH = os.path.dirname(os.path.realpath(__file__))


def run_process(command):
	with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
		return proc.stdout.read()


def commit(repo, message):
	os.chdir(os.path.join(BASE_PATH, repo))
	run_process(['git', 'add', 'data.txt', message])
	run_process(['git', 'commit', '-m', message])
	os.chdir(BASE_PATH)


def load_json_file(filename):
	with open('json/{}'.format(filename), 'r') as jsonfile:
		return json.load(jsonfile)


class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.render('index.html')


class RepoHandler(tornado.web.RequestHandler):
	def get(self, user, repo):
		if os.path.exists(os.path.join('data', user, repo, 'data.txt')):
			with open(os.path.join('data', user, repo, 'data.txt')) as data_file:
				data = ''.join(data_file.readlines()).replace('\n', ' ').replace('$NEWLINE', '\n')
			self.render('repo.html', data=data, user=user, repo=repo)
		else:
			self.finish('REPO NOT FOUND')

	def post(self, user, repo):
		data = self.get_argument('data').replace('\n', '$NEWLINE').replace(' ', '\n')
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
