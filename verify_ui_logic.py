import unittest
import os
import sqlite3
from student_system import app, init_db, get_db

class UILogicTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Reset database for testing
        with app.app_context():
            init_db()
            db = get_db()
            # Clear existing data
            db.execute("DELETE FROM students")
            db.execute("DELETE FROM tutors")
            db.execute("DELETE FROM selections")
            
            # Insert test students
            students = [
                ('201', 'StudentA', '123456', 'M', 'CS', 'Class1', '2023', '123', 'Active', '组长', 'GroupA', 'CollegeA'),
                ('202', 'StudentB', '123456', 'F', 'CS', 'Class1', '2023', '124', 'Active', '成员', 'GroupA', 'CollegeA'),
                ('203', 'StudentC', '123456', 'M', 'CS', 'Class1', '2023', '125', 'Active', '成员', None, 'CollegeA')
            ]
            db.executemany('INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', students)
            
            # Insert test tutors
            tutors = [
                ('T01', 'ProfA', 'CS', 'AI', 5, 0, 'DescA'),
                ('T02', 'ProfB', 'CS', 'SE', 5, 0, 'DescB'),
            ]
            db.executemany('INSERT INTO tutors VALUES (?,?,?,?,?,?,?)', tutors)
            db.commit()

    def login(self, username):
        with self.client.session_transaction() as sess:
            sess['user_id'] = username

    def test_group_restriction(self):
        self.login('201') # Already in group
        
        # Try to create group
        response = self.client.get('/create_group', follow_redirects=True)
        self.assertIn(b'\xe4\xbd\xa0\xe5\xb7\xb2\xe7\xbb\x8f\xe5\x8a\xa0\xe5\x85\xa5\xe5\xb0\x8f\xe7\xbb\x84', response.data) # "你已经加入小组"

        # Try to join another group
        # First create another group
        with app.app_context():
            db = get_db()
            db.execute("UPDATE students SET group_name='GroupB', role='组长' WHERE id='203'")
            db.commit()
            
        response = self.client.get('/join_group/GroupB', follow_redirects=True)
        self.assertIn(b'\xe4\xbd\xa0\xe5\xb7\xb2\xe7\xbb\x8f\xe6\x9c\x89\xe5\xb0\x8f\xe7\xbb\x84\xe4\xba\x86', response.data) # "你已经有小组了"

    def test_tutor_selection(self):
        self.login('203') # No group, but can select tutor
        
        # Get page
        response = self.client.get('/select_tutor')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ProfA', response.data)
        
        # Submit selection
        response = self.client.post('/select_tutor', data={
            'choice_1': 'T01',
            'choice_2': 'T02',
            'choice_3': ''
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xbf\x97\xe6\x84\xbf\xe6\x8f\x90\xe4\xba\xa4\xe6\x88\x90\xe5\x8a\x9f', response.data) # "志愿提交成功"
        
        # Verify DB
        with app.app_context():
            db = get_db()
            sel = db.execute("SELECT * FROM selections WHERE student_id='203'").fetchone()
            self.assertEqual(sel['choice_1'], 'T01')
            self.assertEqual(sel['choice_2'], 'T02')

    def test_password_reset(self):
        # Test success
        response = self.client.post('/reset_password', data={
            'id': '201',
            'name': 'StudentA',
            'new_password': 'newpass',
            'confirm_password': 'newpass'
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xaf\x86\xe7\xa0\x81\xe9\x87\x8d\xe7\xbd\xae\xe6\x88\x90\xe5\x8a\x9f', response.data) # "密码重置成功"
        
        with app.app_context():
            db = get_db()
            u = db.execute("SELECT password FROM students WHERE id='201'").fetchone()
            self.assertEqual(u['password'], 'newpass')

        # Test fail (wrong name)
        response = self.client.post('/reset_password', data={
            'id': '201',
            'name': 'WrongName',
            'new_password': 'p',
            'confirm_password': 'p'
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xad\xa6\xe5\x8f\xb7\xe6\x88\x96\xe5\xa7\x93\xe5\x90\x8d\xe9\x94\x99\xe8\xaf\xaf', response.data) # "学号或姓名错误"

    def test_profile_password_change(self):
        self.login('201')
        
        # Get profile page
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'StudentA', response.data)
        
        # Change password success
        response = self.client.post('/profile', data={
            'old_password': '123456',
            'new_password': 'newpass2',
            'confirm_password': 'newpass2'
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xaf\x86\xe7\xa0\x81\xe4\xbf\xae\xe6\x94\xb9\xe6\x88\x90\xe5\x8a\x9f', response.data) # "密码修改成功"
        
        # Verify DB
        with app.app_context():
            db = get_db()
            u = db.execute("SELECT password FROM students WHERE id='201'").fetchone()
            self.assertEqual(u['password'], 'newpass2')
            
        # Change password fail (wrong old pass)
        self.login('201')
        
        response = self.client.post('/profile', data={
            'old_password': 'wrong',
            'new_password': 'p',
            'confirm_password': 'p'
        }, follow_redirects=True)
        self.assertIn(b'\xe5\x8e\x9f\xe5\xaf\x86\xe7\xa0\x81\xe9\x94\x99\xe8\xaf\xaf', response.data) # "原密码错误"

    def test_topic_and_selection_permissions(self):
        # 1. Leader (201) submits topic
        self.login('201')
        response = self.client.post('/submit_topic', data={
            'direction': 'AI Research',
            'introduction': 'Deep Learning'
        }, follow_redirects=True)
        self.assertIn(b'\xe8\xaf\xbe\xe9\xa2\x98\xe6\x8f\x90\xe4\xba\xa4\xe6\x88\x90\xe5\x8a\x9f', response.data) # "课题提交成功"
        
        # Verify DB
        with app.app_context():
            db = get_db()
            topic = db.execute("SELECT * FROM topics WHERE group_name='GroupA'").fetchone()
            self.assertIsNotNone(topic)
            self.assertEqual(topic['direction'], 'AI Research')
            
            # Verify Notification to Member (202)
            msg = db.execute("SELECT * FROM messages WHERE receiver_id='202' AND type='system'").fetchone()
            self.assertIsNotNone(msg)
            self.assertIn('AI Research', msg['content'])

        # 2. Member (202) tries to submit topic -> Fail
        self.login('202')
        response = self.client.get('/submit_topic', follow_redirects=True)
        self.assertIn(b'\xe5\x8f\xaa\xe6\x9c\x89\xe7\xbb\x84\xe9\x95\xbf\xe5\x8f\xaf\xe4\xbb\xa5', response.data) # "只有组长可以"
        
        # 3. Member (202) tries to select tutor -> Fail
        response = self.client.get('/select_tutor', follow_redirects=True)
        self.assertIn(b'\xe5\x8f\xaa\xe6\x9c\x89\xe7\xbb\x84\xe9\x95\xbf\xe5\x8f\xaf\xe4\xbb\xa5', response.data) # "只有组长可以"
        
        # 4. Leader (201) selects tutor -> Success & Notification
        self.login('201')
        response = self.client.post('/select_tutor', data={
            'choice_1': '1001'
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xbf\x97\xe6\x84\xbf\xe6\x8f\x90\xe4\xba\xa4\xe6\x88\x90\xe5\x8a\x9f', response.data) # "志愿提交成功"
        
        # Verify Notification
        with app.app_context():
            db = get_db()
            msgs = db.execute("SELECT * FROM messages WHERE receiver_id='202' AND type='system'").fetchall()
            # Should have 2 messages now (1 topic, 1 tutor)
            self.assertEqual(len(msgs), 2)
            self.assertIn('导师志愿', msgs[1]['content'])

if __name__ == '__main__':
    unittest.main()
