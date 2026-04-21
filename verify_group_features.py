import unittest
import os
import sqlite3
from student_system import app, init_db, get_db

class GroupFeaturesTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.db_path = 'student_system_final_v2.db'
        
        # Reset database for testing
        with app.app_context():
            init_db()
            db = get_db()
            # Clear existing data for clean test
            db.execute("DELETE FROM students")
            db.execute("DELETE FROM messages")
            
            # Insert test students
            students = [
                ('101', 'UserA', '123456', '男', 'CS', 'Class1', '2023', '', 'Active', '成员', None),
                ('102', 'UserB', '123456', '男', 'CS', 'Class1', '2023', '', 'Active', '成员', None),
                ('103', 'UserC', '123456', '男', 'CS', 'Class1', '2023', '', 'Active', '成员', None),
                ('104', 'UserD', '123456', '男', 'CS', 'Class1', '2023', '', 'Active', '成员', None),
                ('105', 'UserE', '123456', '男', 'CS', 'Class1', '2023', '', 'Active', '成员', None),
                ('106', 'UserF', '123456', '男', 'SE', 'Class2', '2023', '', 'Active', '成员', None), # Diff Major
            ]
            db.executemany('INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?)', students)
            db.commit()

    def login(self, username):
        with self.client.session_transaction() as sess:
            sess['user_id'] = username

    def test_create_group_limit(self):
        self.login('101')
        # Create group with 3 members (total 4)
        response = self.client.post('/create_group_submit', data={
            'group_name': 'Group1',
            'members': ['102', '103', '104']
        }, follow_redirects=True)
        self.assertIn(b'\xe5\xb0\x8f\xe7\xbb\x84\xe6\x93\x8d\xe4\xbd\x9c\xe6\x88\x90\xe5\x8a\x9f', response.data) # "小组操作成功"

        # Verify DB
        with app.app_context():
            db = get_db()
            count = db.execute("SELECT count(*) FROM students WHERE group_name='Group1'").fetchone()[0]
            self.assertEqual(count, 4)

        # Try to create group with 4 members (total 5) - Should fail
        self.login('105') # UserE
        response = self.client.post('/create_group_submit', data={
            'group_name': 'Group2',
            'members': ['101', '102', '103', '104'] # Already in group, but logic checks count first
        }, follow_redirects=True)
        # Check for error message (utf-8 encoded)
        self.assertIn(b'\xe5\xb0\x8f\xe7\xbb\x84\xe4\xba\xba\xe6\x95\xb0\xe6\x9c\x80\xe5\xa4\x9a\xe4\xb8\xba4\xe4\xba\xba', response.data) # "小组人数最多为4人"

    def test_dissolve_group(self):
        # Setup group
        with app.app_context():
            db = get_db()
            db.execute("UPDATE students SET group_name='GroupX', role='组长' WHERE id='101'")
            db.execute("UPDATE students SET group_name='GroupX', role='成员' WHERE id='102'")
            db.commit()

        self.login('101')
        self.client.get('/dissolve_group', follow_redirects=True)
        
        with app.app_context():
            db = get_db()
            u1 = db.execute("SELECT group_name FROM students WHERE id='101'").fetchone()
            u2 = db.execute("SELECT group_name FROM students WHERE id='102'").fetchone()
            self.assertIsNone(u1['group_name'])
            self.assertIsNone(u2['group_name'])

    def test_leave_group(self):
        # Setup group
        with app.app_context():
            db = get_db()
            db.execute("UPDATE students SET group_name='GroupY', role='组长' WHERE id='101'")
            db.execute("UPDATE students SET group_name='GroupY', role='成员' WHERE id='102'")
            db.commit()

        self.login('102')
        self.client.get('/leave_group', follow_redirects=True)
        
        with app.app_context():
            db = get_db()
            u2 = db.execute("SELECT group_name FROM students WHERE id='102'").fetchone()
            self.assertIsNone(u2['group_name'])
            # Leader still there
            u1 = db.execute("SELECT group_name FROM students WHERE id='101'").fetchone()
            self.assertEqual(u1['group_name'], 'GroupY')

    def test_join_group(self):
        # Setup group with 1 member
        with app.app_context():
            db = get_db()
            db.execute("UPDATE students SET group_name='GroupZ', role='组长' WHERE id='101'")
            db.commit()

        self.login('102')
        self.client.get('/join_group/GroupZ', follow_redirects=True)
        
        with app.app_context():
            db = get_db()
            u2 = db.execute("SELECT group_name FROM students WHERE id='102'").fetchone()
            self.assertEqual(u2['group_name'], 'GroupZ')

    def test_invite_flow(self):
        # Setup group
        with app.app_context():
            db = get_db()
            db.execute("UPDATE students SET group_name='GroupI', role='组长' WHERE id='101'")
            db.commit()

        self.login('101')
        # Invite 102
        self.client.get('/invite_member/102')
        
        with app.app_context():
            db = get_db()
            msg = db.execute("SELECT * FROM messages WHERE receiver_id='102'").fetchone()
            self.assertIsNotNone(msg)
            self.assertEqual(msg['type'], 'invite')

        # 102 accepts
        self.login('102')
        self.client.get(f"/handle_invite/{msg['id']}/accept", follow_redirects=True)
        
        with app.app_context():
            db = get_db()
            u2 = db.execute("SELECT group_name FROM students WHERE id='102'").fetchone()
            self.assertEqual(u2['group_name'], 'GroupI')
            msg = db.execute("SELECT status FROM messages WHERE id=?", (msg['id'],)).fetchone()
            self.assertEqual(msg['status'], 'accepted')

if __name__ == '__main__':
    unittest.main()
