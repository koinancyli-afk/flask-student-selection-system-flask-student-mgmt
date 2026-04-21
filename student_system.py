import csv
import sqlite3
import os
import sys
import socket
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, g, flash
from jinja2 import DictLoader

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'

# ==========================================
# 核心修复：使用绝对路径定位文件 & 强制重置数据库
# ==========================================
# 获取当前脚本所在的绝对路径目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ！！注意：为了强制重新导入 CSV，数据库文件名再次改变
DB_FILE = os.path.join(BASE_DIR, 'student_system_final_v2.db')
EXCEL_FILE = os.path.join(BASE_DIR, '学生名单.xls')

print(f"\n--- 系统路径调试 ---")
print(f"代码所在目录: {BASE_DIR}")
print(f"【数据库路径】: {DB_FILE}")
print(f"【Excel预期路径】: {EXCEL_FILE}")

if os.path.exists(EXCEL_FILE):
    print(">>> 检测结果：Excel 文件存在！")
else:
    print("!!! 警告：Excel 文件不存在！请确认文件名是否 EXACTLY '学生名单.xls' 并在同一目录。")
print(f"--------------------\n")


# ==========================================
# 1. 数据库管理
# ==========================================

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_FILE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库并导入CSV数据"""
    # 检查表是否存在，如果数据足够多，则说明已经初始化过，跳过
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            # 检查学生数量，大于100个才算成功导入过
            c.execute("SELECT count(*) FROM students")
            count = c.fetchone()[0]
            if count > 100:
                print(f">>> 数据库已存在且包含 {count} 条学生数据，跳过初始化。")
                
                # --- 数据库升级 ---
                # 1. 确保 messages 表存在
                c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT,
                    receiver_id TEXT,
                    type TEXT,
                    content TEXT,
                    group_name TEXT,
                    status TEXT DEFAULT 'unread',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                # 2. 确保 topics 表存在
                c.execute('''CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT,
                    direction TEXT,
                    introduction TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                # 3. 尝试添加 college 字段 (如果不存在)
                try:
                    c.execute("ALTER TABLE students ADD COLUMN college TEXT")
                except sqlite3.OperationalError:
                    pass # 字段已存在
                
                # 4. 强制更新导师数据
                c.execute('DELETE FROM tutors')  # 清空旧导师数据
                tutors_data = [
                    ('1001', '向函', '计算机科学与技术', '人工智能', 3, 0, '研究方向：人工智能与机器学习'),
                    ('1002', '丘文峰', '信息管理与信息系统', '大数据分析', 3, 0, '研究方向：大数据挖掘与分析'),
                    ('1003', '吴应江', '软件工程', '软件开发', 3, 0, '研究方向：软件工程与项目管理'),
                    ('1004', '白金山', '计算机科学与技术', '云计算', 3, 0, '研究方向：云计算与分布式系统'),
                    ('1005', '赵云', '信息安全', '网络安全', 3, 0, '研究方向：网络安全与密码学'),
                    ('1006', '杨小宝', '数据科学', '数据挖掘', 3, 0, '研究方向：数据科学与可视化'),
                    ('1007', '侯洁', '计算机科学与技术', '图像处理', 3, 0, '研究方向：计算机视觉与图像处理'),
                    ('1008', '张春明', '软件工程', 'Web开发', 3, 0, '研究方向：Web技术与应用'),
                    ('1009', '李松涛', '信息管理与信息系统', '信息系统', 3, 0, '研究方向：信息系统开发与管理'),
                    ('1010', '谢翠萍', '计算机科学与技术', '算法设计', 3, 0, '研究方向：算法设计与优化'),
                    ('1011', '夏峰', '人工智能', '深度学习', 3, 0, '研究方向：深度学习与神经网络'),
                    ('1012', '韩成虎', '软件工程', '移动开发', 3, 0, '研究方向：移动应用开发'),
                    ('1013', '尚文刚', '计算机科学与技术', '物联网', 3, 0, '研究方向：物联网技术'),
                    ('1014', '欧阳东', '信息管理与信息系统', '商业智能', 3, 0, '研究方向：商业智能与决策支持'),
                    ('1015', '郑金秋', '数据科学', '机器学习', 3, 0, '研究方向：机器学习应用'),
                    ('1016', '肖文芳', '计算机科学与技术', '区块链', 3, 0, '研究方向：区块链技术与应用')
                ]
                c.executemany('INSERT INTO tutors VALUES (?,?,?,?,?,?,?)', tutors_data)
                print(">>> 导师数据已更新为16位新导师")
                    
                conn.commit()
                conn.close()
                return
            conn.close()
        except:
            pass  # 如果出错，说明可能损坏，继续下面的重建流程

    print(">>> 正在初始化全新的数据库...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 创建学生表
    c.execute('''DROP TABLE IF EXISTS students''')
    c.execute('''CREATE TABLE students (
        id TEXT PRIMARY KEY,
        name TEXT,
        password TEXT,
        gender TEXT,
        major TEXT,
        class_name TEXT,
        grade TEXT,
        contact TEXT,
        status TEXT,
        role TEXT DEFAULT '成员',
        group_name TEXT,
        college TEXT
    )''')

    # 2. 创建导师表
    c.execute('''DROP TABLE IF EXISTS tutors''')
    c.execute('''CREATE TABLE tutors (
        id TEXT PRIMARY KEY,
        name TEXT,
        dept TEXT,
        direction TEXT,
        limit_num INTEGER,
        current_num INTEGER DEFAULT 0,
        description TEXT
    )''')
    
    # 3. 创建志愿表
    c.execute('''DROP TABLE IF EXISTS selections''')
    c.execute('''CREATE TABLE selections (
        student_id TEXT PRIMARY KEY,
        choice_1 TEXT,
        choice_2 TEXT,
        choice_3 TEXT
    )''')
    
    # 4. 创建消息表
    c.execute('''DROP TABLE IF EXISTS messages''')
    c.execute('''CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id TEXT,
        receiver_id TEXT,
        type TEXT,
        content TEXT,
        group_name TEXT,
        status TEXT DEFAULT 'unread',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 5. 创建课题表
    c.execute('''DROP TABLE IF EXISTS topics''')
    c.execute('''CREATE TABLE topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT,
        direction TEXT,
        introduction TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # --- 导入 Excel 数据 ---
    print(f">>> 尝试从路径 {EXCEL_FILE} 读取文件...")
    if os.path.exists(EXCEL_FILE):
        print(f">>> 文件存在，开始读取...")
        try:
            df = pd.read_excel(EXCEL_FILE)
            count = 0
            for index, row in df.iterrows():
                # 处理 BOM 头
                sid = str(row.get('学号', '')).strip()
                if not sid or sid == 'nan': continue

                # 默认密码 123456
                c.execute('''INSERT OR IGNORE INTO students 
                    (id, name, password, gender, major, class_name, grade, contact, status, role, group_name, college) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (
                              sid,
                              str(row.get('姓名', '')).strip(),
                              "123456",
                              str(row.get('性别', '')).strip(),
                              str(row.get('专业', '')).strip(),
                              str(row.get('班级', '')).strip(),
                              str(row.get('年级', '')).strip(),
                              str(row.get('手机号码', '')).strip() if not pd.isna(row.get('手机号码')) else '',
                              str(row.get('学籍状态', '')).strip() if not pd.isna(row.get('学籍状态')) else '在读',
                              "成员",
                              None,
                              str(row.get('学院', '')).strip() if not pd.isna(row.get('学院')) else '信息管理学院' # 默认学院
                          )
                          )
                count += 1
            print(f">>> 成功导入 {count} 名学生数据！")
        except Exception as e:
            print(f"!!! 导入Excel严重错误: 文件存在但读取失败，错误信息: {e}")
    else:
        print("!!! 错误：无法找到 CSV 文件，将仅写入少量测试数据。")
        # 写入测试数据，确保程序能运行
        c.execute("INSERT OR IGNORE INTO students (id, name, password, gender, major, class_name, grade, contact, status, role, group_name, college) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  ('0000000000', '测试用户', '123456', '男', '计算机科学', 'CS101', '2023', '13800000000', '在读', '成员', None, '计算机学院'))
        conn.commit()
        print(">>> 已写入少量测试数据。")
    
    # 插入默认导师
    tutors_data = [
        ('1001', '向函', '计算机科学与技术', '人工智能', 5, 0, '研究方向：人工智能与机器学习'),
        ('1002', '丘文峰', '信息管理与信息系统', '大数据分析', 5, 0, '研究方向：大数据挖掘与分析'),
        ('1003', '吴应江', '软件工程', '软件开发', 5, 0, '研究方向：软件工程与项目管理'),
        ('1004', '白金山', '计算机科学与技术', '云计算', 5, 0, '研究方向：云计算与分布式系统'),
        ('1005', '赵云', '信息安全', '网络安全', 5, 0, '研究方向：网络安全与密码学'),
        ('1006', '杨小宝', '数据科学', '数据挖掘', 5, 0, '研究方向：数据科学与可视化'),
        ('1007', '侯洁', '计算机科学与技术', '图像处理', 5, 0, '研究方向：计算机视觉与图像处理'),
        ('1008', '张春明', '软件工程', 'Web开发', 5, 0, '研究方向：Web技术与应用'),
        ('1009', '李松涛', '信息管理与信息系统', '信息系统', 5, 0, '研究方向：信息系统开发与管理'),
        ('1010', '谢翠萍', '计算机科学与技术', '算法设计', 5, 0, '研究方向：算法设计与优化'),
        ('1011', '夏峰', '人工智能', '深度学习', 5, 0, '研究方向：深度学习与神经网络'),
        ('1012', '韩成虎', '软件工程', '移动开发', 5, 0, '研究方向：移动应用开发'),
        ('1013', '尚文刚', '计算机科学与技术', '物联网', 3, 0, '研究方向：物联网技术'),
        ('1014', '欧阳东', '信息管理与信息系统', '商业智能', 3, 0, '研究方向：商业智能与决策支持'),
        ('1015', '郑金秋', '数据科学', '机器学习', 3, 0, '研究方向：机器学习应用'),
        ('1016', '肖文芳', '计算机科学与技术', '区块链', 3, 0, '研究方向：区块链技术与应用')
    ]
    c.executemany('INSERT OR IGNORE INTO tutors VALUES (?,?,?,?,?,?,?)', tutors_data)

    conn.commit()
    conn.close()
    print(">>> 数据库初始化完成。")


# ==========================================
# 2. HTML 模板
# ==========================================

TEMPLATES = {
    'base.html': """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>师生双选系统</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body { font-family: 'Inter', 'Microsoft YaHei', sans-serif; background-color: #f8fafc; background-image: radial-gradient(circle at 10% 20%, rgb(239, 246, 255) 0%, rgb(255, 255, 255) 90%); }
            
            /* Liquid Glass Navbar Styles */
            .glass-nav {
                background: rgba(255, 255, 255, 0.65);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.5);
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
            }
            
            .nav-item {
                position: relative;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                border-radius: 16px;
                margin: 4px 12px;
                overflow: hidden;
            }
            
            .nav-item::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, rgba(255,255,255,0.8), rgba(255,255,255,0.2));
                opacity: 0;
                transition: opacity 0.4s ease;
                z-index: -1;
            }
            
            .nav-item.active {
                color: #2563eb;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(37, 99, 235, 0.15);
                transform: translateY(-1px);
            }
            
            .nav-item.active::before {
                opacity: 1;
            }
            
            .nav-item:hover:not(.active) {
                background: rgba(255, 255, 255, 0.4);
                transform: translateY(-1px);
            }
            
            /* Liquid Indicator */
            .nav-item.active::after {
                content: '';
                position: absolute;
                left: 0;
                top: 50%;
                transform: translateY(-50%);
                width: 4px;
                height: 24px;
                background: #2563eb;
                border-radius: 0 4px 4px 0;
                box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
            }

            ::-webkit-scrollbar { width: 6px; height: 6px; }
            ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
            
            /* Animations */
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .fade-in { animation: fadeIn 0.5s ease-out forwards; }
            .hover-scale { transition: transform 0.2s; }
            .hover-scale:hover { transform: scale(1.02); }
            
            .glass { background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.5); }
            .btn-premium { background: linear-gradient(135deg, #3b82f6, #2563eb); box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3); transition: all 0.3s; }
            .btn-premium:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(37, 99, 235, 0.4); }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body class="h-screen flex overflow-hidden text-gray-700">
        <!-- Floating Glass Sidebar -->
        <div class="w-72 p-4 flex flex-col z-20 relative">
            <div class="glass-nav h-full rounded-3xl flex flex-col overflow-hidden relative">
                <!-- Decorative blurred orbs behind glass -->
                <div class="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-blue-100/50 to-transparent pointer-events-none"></div>
                
                <div class="h-20 flex items-center justify-center relative z-10">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-500/30">
                            <i class="fas fa-graduation-cap text-lg"></i>
                        </div>
                        <h1 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">双选系统</h1>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto py-4 space-y-1 relative z-10 custom-scrollbar">
                    <div class="px-4 mb-2 text-xs font-bold text-gray-400 uppercase tracking-wider">菜单</div>
                    
                    <a href="{{ url_for('create_group') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'create_group' else '' }}">
                        <i class="fas fa-users-cog w-6 text-lg {{ 'text-blue-500' if page == 'create_group' else 'text-gray-400' }}"></i> 
                        <span class="font-medium">创建小组</span>
                    </a>
                    <a href="{{ url_for('my_group') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'my_group' else '' }}">
                        <i class="fas fa-users w-6 text-lg {{ 'text-blue-500' if page == 'my_group' else 'text-gray-400' }}"></i>
                        <span class="font-medium">我的小组</span>
                    </a>
                    <a href="{{ url_for('select_tutor') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'select_tutor' else '' }}">
                        <i class="fas fa-chalkboard-teacher w-6 text-lg {{ 'text-blue-500' if page == 'select_tutor' else 'text-gray-400' }}"></i>
                        <span class="font-medium">导师选择</span>
                    </a>
                    <a href="{{ url_for('view_groups') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'view_groups' else '' }}">
                        <i class="fas fa-list-ul w-6 text-lg {{ 'text-blue-500' if page == 'view_groups' else 'text-gray-400' }}"></i>
                        <span class="font-medium">查看小组</span>
                    </a>
                    <a href="{{ url_for('messages') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'messages' else '' }}">
                        <div class="relative">
                            <i class="fas fa-envelope w-6 text-lg {{ 'text-blue-500' if page == 'messages' else 'text-gray-400' }}"></i>
                            {% if unread_count > 0 %}
                            <span id="sidebarBadge" class="absolute -top-1.5 -right-1 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[1.25rem] text-center shadow-sm border border-white">
                                {{ unread_count if unread_count < 100 else '99+' }}
                            </span>
                            {% endif %}
                        </div>
                        <span class="ml-1 font-medium">消息通知</span>
                    </a>
                    {% if user.role == '组长' %}
                    <a href="{{ url_for('submit_topic') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'submit_topic' else '' }}">
                        <i class="fas fa-file-alt w-6 text-lg {{ 'text-blue-500' if page == 'submit_topic' else 'text-gray-400' }}"></i>
                        <span class="font-medium">课题提交</span>
                    </a>
                    {% endif %}
                    
                    <div class="px-4 mt-6 mb-2 text-xs font-bold text-gray-400 uppercase tracking-wider">账户</div>
                    
                    <a href="{{ url_for('profile') }}" class="nav-item flex items-center px-5 py-3.5 text-gray-600 {{ 'active' if page == 'profile' else '' }}">
                        <i class="fas fa-user w-6 text-lg {{ 'text-blue-500' if page == 'profile' else 'text-gray-400' }}"></i>
                        <span class="font-medium">个人中心</span>
                    </a>
                    
                    <div class="mx-5 my-2 border-t border-gray-200/50"></div>
                    
                    <a href="{{ url_for('logout') }}" onclick="return confirm('确定要退出登录吗？')" class="nav-item flex items-center px-5 py-3.5 text-red-500 hover:bg-red-50 transition-colors">
                        <i class="fas fa-sign-out-alt w-6 text-lg"></i>
                        <span class="font-medium">退出登录</span>
                    </a>
                </div>
                
                <div class="p-4 mt-auto relative z-10">
                    <div class="glass p-3 rounded-2xl flex items-center gap-3 border border-white/60 shadow-sm">
                        <div class="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-100 to-purple-100 flex items-center justify-center text-blue-600 font-bold shadow-inner">
                            {{ user.name[0] }}
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-bold text-gray-800 truncate">{{ user.name }}</p>
                            <p class="text-xs text-gray-500 truncate">{{ user.major }}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="flex-1 flex flex-col min-w-0 overflow-hidden relative">
            <!-- Background decoration for main area -->
            <div class="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-blue-50/50 via-white to-purple-50/30 -z-10"></div>
            <div class="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-purple-200/20 rounded-full blur-3xl -z-10"></div>
            
            <main class="flex-1 overflow-auto p-4 md:p-8 relative fade-in">
                {% with messages = get_flashed_messages(with_categories=true) %}
                  {% if messages %}
                    <div id="flashMessages" class="fixed top-6 right-6 z-50 flex flex-col gap-2">
                    {% for category, message in messages %}
                      <div class="flash-message bg-white border-l-4 border-{{ 'green' if category=='success' else 'red' }}-500 shadow-lg rounded p-4 w-80 transition-all duration-300 opacity-100">
                        <div class="flex items-center justify-between">
                          <p class="text-sm text-gray-700 flex-1">{{ message }}</p>
                          <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-400 hover:text-gray-600">
                            <i class="fas fa-times"></i>
                          </button>
                        </div>
                      </div>
                    {% endfor %}
                    </div>
                    <script>
                      // 自动关闭弹窗
                      setTimeout(() => {
                        const messages = document.querySelectorAll('.flash-message');
                        messages.forEach(msg => {
                          msg.classList.add('opacity-0', 'translate-x-4');
                          setTimeout(() => msg.remove(), 300);
                        });
                      }, 3000);
                    </script>
                  {% endif %}
                {% endwith %}
                {% block content %}{% endblock %}
            </main>
        </div>
    </body>
    </html>
    """,

    'login.html': """
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <title>学生双选系统 - 登录</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { 
                font-family: 'Inter', sans-serif; 
                margin: 0;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                background-color: #0f172a;
            }

            /* Starry Sky Background */
            #star-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
                pointer-events: none;
            }
            
            .star {
                position: absolute;
                background: white;
                border-radius: 50%;
                opacity: 0;
                animation: twinkle linear infinite;
            }
            
            @keyframes twinkle {
                0% { opacity: 0; transform: translateY(0) scale(0.5); }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { opacity: 0; transform: translateY(-100px) scale(1); }
            }

            /* Dark Liquid Glass Card */
            .login-card {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.3);
                width: 440px;
                padding: 48px;
                opacity: 0;
                animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                position: relative;
                overflow: hidden;
            }
            
            /* Shine effect */
            .login-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent);
                transform: skewX(-25deg);
                animation: shine 6s infinite;
                pointer-events: none;
            }
            
            @keyframes shine {
                0%, 100% { left: -100%; }
                30% { left: 200%; }
            }

            @keyframes slideUp {
                to { opacity: 1; }
            }

            .input-field {
                width: 100%;
                padding: 14px 16px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                outline: none;
                transition: all 0.3s ease;
                color: #ffffff;
                font-size: 15px;
            }
            
            .input-field::placeholder { color: rgba(255, 255, 255, 0.6); }
            
            .input-field:focus {
                background: rgba(255, 255, 255, 0.2);
                border-color: rgba(255, 255, 255, 0.5);
                box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.1);
                transform: translateY(-1px);
            }

            .checkbox-wrapper {
                display: flex;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                color: rgba(255, 255, 255, 0.8);
                font-size: 14px;
                user-select: none;
            }
            
            .checkbox-wrapper input {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.4);
                background: rgba(255, 255, 255, 0.1);
                cursor: pointer;
                accent-color: #3b82f6;
            }

            .link-hover {
                position: relative;
                color: #60a5fa;
                text-decoration: none;
                font-size: 14px;
                transition: color 0.2s;
            }
            
            .link-hover:hover { color: #93c5fd; }
            
            /* Button Ripple Effect */
            .btn-ripple {
                position: relative;
                overflow: hidden;
            }
            
            .ripple {
                position: absolute;
                border-radius: 50%;
                transform: scale(0);
                animation: ripple 0.6s linear;
                background-color: rgba(255, 255, 255, 0.3);
            }
            
            @keyframes ripple {
                to { transform: scale(4); opacity: 0; }
            }
        </style>
    </head>
    <body>
        <div id="star-container"></div>
        
        <div class="login-card" id="loginCard">
            <!-- Reverted Logo: Icon + Text -->
            <div class="flex flex-col items-center mb-10">
                <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg mb-4 transform rotate-3 hover:rotate-6 transition-transform duration-300 border border-white/20">
                    <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                </div>
                <h1 class="text-2xl font-bold text-white tracking-tight shadow-sm">学生双选系统</h1>
                <p class="text-blue-200 text-sm mt-2">欢迎回来，请登录您的账户</p>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="mb-6 p-3 rounded-lg text-sm flex items-center gap-2 {{ 'bg-red-500/20 text-red-200 border border-red-500/30' if category == 'error' else 'bg-green-500/20 text-green-200 border border-green-500/30' }}">
                            <span class="w-1.5 h-1.5 rounded-full {{ 'bg-red-400' if category == 'error' else 'bg-green-400' }}"></span>
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST" class="space-y-5">
                <div>
                    <input type="text" name="username" required placeholder="账户" class="input-field">
                </div>
                
                <div>
                    <input type="password" name="password" required placeholder="密码" class="input-field">
                </div>

                <div class="flex items-center justify-center pt-2">
                    <label class="checkbox-wrapper">
                        <input type="checkbox" name="remember">
                        保持我的登录状态
                    </label>
                </div>

                <div class="text-center pt-4">
                    <a href="{{ url_for('reset_password') }}" class="link-hover">忘记了密码?</a>
                </div>

                <button type="submit" class="w-full mt-6 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-blue-900/30 transform hover:-translate-y-0.5 transition-all duration-300 btn-ripple">
                    登录
                </button>
            </form>
        </div>
        
        <script>
            // JS Star Generator
            document.addEventListener('DOMContentLoaded', () => {
                const container = document.getElementById('star-container');
                if (container) {
                    for (let i = 0; i < 100; i++) {
                        const star = document.createElement('div');
                        star.className = 'star';
                        star.style.left = `${Math.random() * 100}%`;
                        star.style.top = `${Math.random() * 100}%`;
                        const size = Math.random() * 2 + 1;
                        star.style.width = `${size}px`;
                        star.style.height = `${size}px`;
                        star.style.animationDuration = `${Math.random() * 3 + 2}s`;
                        star.style.animationDelay = `${Math.random() * 5}s`;
                        container.appendChild(star);
                    }
                }
            });

            // Button Ripple Effect
            const buttons = document.querySelectorAll('.btn-ripple');
            buttons.forEach(btn => {
                btn.addEventListener('click', function(e) {
                    const x = e.clientX - e.target.getBoundingClientRect().left;
                    const y = e.clientY - e.target.getBoundingClientRect().top;
                    
                    const ripples = document.createElement('span');
                    ripples.style.left = x + 'px';
                    ripples.style.top = y + 'px';
                    ripples.classList.add('ripple');
                    this.appendChild(ripples);
                    
                    setTimeout(() => {
                        ripples.remove();
                    }, 600);
                });
            });
        </script>
    </body>
    </html>
    """,

    'reset_password.html': """
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <title>重置密码</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes scale-in {
                0% { opacity: 0; transform: scale(0.95); }
                100% { opacity: 1; transform: scale(1); }
            }
            .animate-scale-in {
                animation: scale-in 0.3s ease-out forwards;
            }
            /* Light Theme Background */
            body {
                background-color: #0f172a;
                overflow: hidden;
            }

            /* Dark Liquid Glass Card */
            .glass-card {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.3);
            }
            
            .input-glass {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #ffffff;
            }
            .input-glass:focus {
                background: rgba(255, 255, 255, 0.2);
                border-color: rgba(255, 255, 255, 0.5);
                box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.1);
            }
        </style>
    </head>
    <body class="h-screen flex items-center justify-center relative overflow-hidden">
        <div id="star-container"></div>
        <div class="glass-card p-10 rounded-3xl w-[500px] relative animate-scale-in">
            <div class="flex justify-between items-center mb-8 border-b border-white/20 pb-4">
                <h1 class="text-xl font-bold text-white">重置密码</h1>
                <a href="{{ url_for('login') }}" class="text-white/60 hover:text-white transition-colors text-2xl leading-none">&times;</a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="mb-6 p-3 rounded-lg text-sm flex items-center gap-2 {{ 'bg-red-50 text-red-600 border border-red-100' if category == 'error' else 'bg-green-50 text-green-600 border border-green-100' }}">
                            <span class="w-1.5 h-1.5 rounded-full {{ 'bg-red-500' if category == 'error' else 'bg-green-500' }}"></span>
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST" class="space-y-6 px-2">
                <div class="flex items-center group">
                    <label class="w-24 text-right mr-4 text-white font-medium">学号：</label>
                    <input type="text" name="id" required class="flex-1 input-glass rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/30 transition-all">
                </div>
                
                <div class="flex items-center group">
                    <label class="w-24 text-right mr-4 text-white font-medium">姓名：</label>
                    <input type="text" name="name" required class="flex-1 input-glass rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/30 transition-all">
                </div>

                <div class="flex items-center group">
                    <label class="w-24 text-right mr-4 text-white font-medium">新密码：</label>
                    <input type="password" name="new_password" required class="flex-1 input-glass rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/30 transition-all">
                </div>

                <div class="flex items-center group">
                    <label class="w-24 text-right mr-4 text-white font-medium">确认密码：</label>
                    <input type="password" name="confirm_password" required class="flex-1 input-glass rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/30 transition-all">
                </div>

                <p class="text-gray-300 text-xs mt-2 ml-28">提示：请输入学号和姓名验证身份，然后设置新密码</p>

                <div class="flex justify-center gap-4 mt-8 pt-4">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-8 rounded-lg shadow-lg shadow-blue-500/30 transition-all transform hover:-translate-y-0.5">重置密码</button>
                    <a href="{{ url_for('login') }}" class="bg-white/10 border border-white/20 hover:bg-white/20 text-white font-medium py-2 px-8 rounded-lg shadow-sm transition-colors">取消</a>
                </div>
            </form>
        </div>
        <script>
            // JS Star Generator
            document.addEventListener('DOMContentLoaded', () => {
                const container = document.getElementById('star-container');
                if (container) {
                    for (let i = 0; i < 100; i++) {
                        const star = document.createElement('div');
                        star.className = 'star';
                        star.style.left = `${Math.random() * 100}%`;
                        star.style.top = `${Math.random() * 100}%`;
                        const size = Math.random() * 2 + 1;
                        star.style.width = `${size}px`;
                        star.style.height = `${size}px`;
                        star.style.animationDuration = `${Math.random() * 3 + 2}s`;
                        star.style.animationDelay = `${Math.random() * 5}s`;
                        container.appendChild(star);
                    }
                }
            });
        </script>
    </body>
    </html>
    """,

    'profile.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="max-w-4xl mx-auto fade-in">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1.5 h-8 bg-blue-600 rounded-full"></span>
            个人中心
        </h2>
        
        <div class="bg-white rounded-xl shadow-sm border p-8 relative">
            <div class="flex justify-end gap-3 mb-6">
                {% if user.group_name %}
                <button onclick="openModal('viewTopicModal')" class="px-4 py-2 bg-purple-50 text-purple-600 rounded-lg text-sm font-bold hover:bg-purple-100 transition">
                    <i class="fas fa-file-alt mr-1"></i> 查看课题
                </button>
                <button onclick="openModal('viewSelectionModal')" class="px-4 py-2 bg-green-50 text-green-600 rounded-lg text-sm font-bold hover:bg-green-100 transition hover-scale">
                    <i class="fas fa-chalkboard-teacher mr-1"></i> 查看志愿
                </button>
                {% endif %}
                <button onclick="openModal('editInfoModal')" class="px-4 py-2 bg-blue-50 text-blue-600 rounded-lg text-sm font-bold hover:bg-blue-100 transition hover-scale">
                    <i class="fas fa-edit mr-1"></i> 编辑资料
                </button>
                <button onclick="openModal('passwordModal')" class="px-4 py-2 bg-gray-50 text-gray-600 rounded-lg text-sm font-bold hover:bg-gray-100 transition hover-scale">
                    <i class="fas fa-key mr-1"></i> 修改密码
                </button>
            </div>

            <div class="flex flex-col items-center mb-8">
                <div class="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 text-3xl font-bold mb-4">
                    {{ user.name[0] }}
                </div>
                <h3 class="text-xl font-bold text-gray-800">{{ user.name }}</h3>
                <p class="text-gray-500 text-sm">{{ user.id }}</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6 max-w-2xl mx-auto text-sm">
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">学院</span>
                    <span class="font-medium">{{ user.college or '未填写' }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">专业</span>
                    <span class="font-medium">{{ user.major }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">班级</span>
                    <span class="font-medium">{{ user.class_name }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">年级</span>
                    <span class="font-medium">{{ user.grade }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">性别</span>
                    <span class="font-medium">{{ user.gender }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2">
                    <span class="text-gray-500">状态</span>
                    <span class="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">{{ user.status }}</span>
                </div>
                <div class="flex justify-between border-b border-gray-50 pb-2 md:col-span-2">
                    <span class="text-gray-500">联系电话</span>
                    <span class="font-medium">{{ user.contact or '未填写' }}</span>
                </div>
            </div>
        </div>
    </div>

        </div>
    </div>

    <!-- 查看课题弹窗 -->
    <div id="viewTopicModal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-lg p-6 transform transition-all scale-95 opacity-0">
            <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">小组课题信息</h3>
            {% if topic %}
            <div class="space-y-4">
                <div>
                    <span class="text-sm text-gray-500 block mb-1">研究方向</span>
                    <p class="font-medium text-gray-900">{{ topic.direction }}</p>
                </div>
                <div>
                    <span class="text-sm text-gray-500 block mb-1">课题简介</span>
                    <p class="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg leading-relaxed">{{ topic.introduction }}</p>
                </div>
                <div class="text-xs text-gray-400 text-right">提交时间: {{ topic.created_at }}</div>
            </div>
            {% else %}
            <div class="py-8 text-center text-gray-500">
                <i class="fas fa-file-excel text-4xl mb-2 opacity-50"></i>
                <p>暂未提交课题</p>
            </div>
            {% endif %}
            <div class="flex justify-end mt-6">
                <button onclick="closeModal('viewTopicModal')" class="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">关闭</button>
            </div>
        </div>
    </div>

    <!-- 查看志愿弹窗 -->
    <div id="viewSelectionModal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 transform transition-all scale-95 opacity-0">
            <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">导师志愿信息</h3>
            {% if selection %}
            <div class="space-y-3">
                {% for item in selection %}
                <div class="flex items-center p-3 bg-blue-50 rounded-lg border border-blue-100">
                    <div class="w-8 h-8 rounded-full bg-blue-200 text-blue-700 flex items-center justify-center font-bold mr-3">{{ loop.index }}</div>
                    <span class="font-medium text-gray-800">{{ item.split(': ')[1] }}</span>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="py-8 text-center text-gray-500">
                <i class="fas fa-user-slash text-4xl mb-2 opacity-50"></i>
                <p>暂未提交导师志愿</p>
            </div>
            {% endif %}
            <div class="flex justify-end mt-6">
                <button onclick="closeModal('viewSelectionModal')" class="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">关闭</button>
            </div>
        </div>
    </div>

    <!-- 编辑资料弹窗 -->
    <div id="editInfoModal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 transform transition-all scale-95 opacity-0" id="editInfoContent">
            <h3 class="text-lg font-bold text-gray-800 mb-6">编辑个人资料</h3>
            <form method="POST" action="{{ url_for('profile') }}">
                <input type="hidden" name="action" value="update_info">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">学院</label>
                        <input type="text" name="college" value="{{ user.college or '' }}" class="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">联系电话</label>
                        <input type="text" name="contact" value="{{ user.contact or '' }}" class="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    </div>
                </div>
                <div class="flex justify-end gap-3 mt-8">
                    <button type="button" onclick="closeModal('editInfoModal')" class="px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg">取消</button>
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">保存</button>
                </div>
            </form>
        </div>
    </div>

    <!-- 修改密码弹窗 -->
    <div id="passwordModal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 transform transition-all scale-95 opacity-0" id="passwordContent">
            <h3 class="text-lg font-bold text-gray-800 mb-6">修改密码</h3>
            <form method="POST" action="{{ url_for('profile') }}">
                <input type="hidden" name="action" value="change_password">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">原密码</label>
                        <input type="password" name="old_password" required class="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">新密码</label>
                        <input type="password" name="new_password" required class="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">确认新密码</label>
                        <input type="password" name="confirm_password" required class="w-full border rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    </div>
                </div>
                <div class="flex justify-end gap-3 mt-8">
                    <button type="button" onclick="closeModal('passwordModal')" class="px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg">取消</button>
                    <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">确认修改</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openModal(id) {
            const modal = document.getElementById(id);
            const content = modal.firstElementChild;
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            // Animation
            setTimeout(() => {
                content.classList.remove('scale-95', 'opacity-0');
                content.classList.add('scale-100', 'opacity-100');
            }, 10);
        }

        function closeModal(id) {
            const modal = document.getElementById(id);
            const content = modal.firstElementChild;
            content.classList.remove('scale-100', 'opacity-100');
            content.classList.add('scale-95', 'opacity-0');
            setTimeout(() => {
                modal.classList.remove('flex');
                modal.classList.add('hidden');
            }, 300);
        }
    </script>
    {% endblock %}
    """,

    'submit_topic.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="max-w-3xl mx-auto fade-in">
        <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <span class="w-1.5 h-8 bg-blue-600 rounded-full"></span>
            课题提交
        </h2>
        
        <div class="bg-white rounded-xl shadow-sm border p-8">
            <form method="POST" class="space-y-6">
                <div>
                    <label class="block text-sm font-bold text-gray-700 mb-2">小组名称</label>
                    <input type="text" value="{{ user.group_name }}" readonly class="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-gray-500 cursor-not-allowed">
                </div>
                
                <div>
                    <label class="block text-sm font-bold text-gray-700 mb-2">研究方向</label>
                    <input type="text" name="direction" required placeholder="请输入课题研究方向" class="w-full border border-gray-200 rounded-lg px-4 py-3 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all">
                </div>
                
                <div>
                    <label class="block text-sm font-bold text-gray-700 mb-2">课题简介</label>
                    <textarea name="introduction" rows="6" required placeholder="请输入课题的详细介绍..." class="w-full border border-gray-200 rounded-lg px-4 py-3 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10 transition-all resize-none"></textarea>
                </div>
                
                <div class="pt-4">
                    <button type="submit" class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 shadow-lg shadow-blue-500/30 transition-all transform hover:-translate-y-0.5">
                        提交课题
                    </button>
                </div>
            </form>
        </div>
    </div>
    {% endblock %}
    """,

    'create_group.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="h-[calc(100vh-6rem)] flex flex-col gap-4 fade-in">
        <div class="flex justify-between items-center">
            <div>
                <h2 class="text-2xl font-bold text-gray-800">组建团队</h2>
                <p class="text-sm text-gray-500 mt-1">当前专业: <span class="text-blue-600 font-bold">{{ user.major }}</span></p>
            </div>
            {% if user.group_name %}
            <div class="bg-yellow-100 text-yellow-800 px-4 py-2 rounded-lg text-sm font-medium">
                当前小组: {{ user.group_name }}
            </div>
            {% endif %}
        </div>

        <div class="flex-1 flex gap-6 min-h-0">
            <!-- 左侧列表 -->
            <div class="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
                <div class="p-4 border-b bg-gray-50 space-y-3">
                    <div class="relative">
                        <i class="fas fa-search absolute left-3 top-3 text-gray-400"></i>
                        <input type="text" id="searchInput" placeholder="搜索同专业未组队同学..." 
                               class="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                               onkeyup="filterStudents()">
                    </div>
                    <!-- 班级筛选 (保留，方便同专业内查找) -->
                    <select id="classFilter" onchange="filterStudents()" class="w-full border rounded-lg px-2 py-1.5 text-sm bg-white">
                        <option value="">所有班级</option>
                        {% for cls in classes %}
                        <option value="{{ cls }}">{{ cls }}</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="flex-1 overflow-y-auto p-2">
                    <div id="studentList" class="grid grid-cols-1 gap-2">
                        {% for s in students %}
                        <div class="student-card flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-blue-50 cursor-pointer group transition hover-scale"
                             data-id="{{ s.id }}" data-name="{{ s.name }}" data-class="{{ s.class_name }}"
                             onclick="addToGroup('{{ s.id }}', '{{ s.name }}', '{{ s.class_name }}')">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-xs font-bold">
                                    {{ s.name[-2:] }}
                                </div>
                                <div>
                                    <div class="text-sm font-medium text-gray-900 flex items-center gap-2">
                                        {{ s.name }}
                                        {% if s.gender == '男' %} <i class="fas fa-mars text-blue-400 text-xs"></i>
                                        {% elif s.gender == '女' %} <i class="fas fa-venus text-pink-400 text-xs"></i> {% endif %}
                                    </div>
                                    <div class="text-xs text-gray-500">{{ s.id }} | {{ s.class_name }}</div>
                                </div>
                            </div>
                            <div class="flex gap-2">
                                <i class="fas fa-plus-circle text-gray-300 hover:text-blue-500 text-xl" onclick="addToGroup('{{ s.id }}', '{{ s.name }}', '{{ s.class_name }}')" title="添加到列表"></i>
                                <i class="fas fa-paper-plane text-gray-300 hover:text-green-500 text-xl" onclick="inviteMember('{{ s.id }}'); event.stopPropagation();" title="发送邀请"></i>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="p-2 border-t bg-gray-50 text-xs text-gray-400 text-center">
                    共 {{ students|length }} 位同专业同学
                </div>
            </div>

            <div class="flex flex-col justify-center text-gray-300"><i class="fas fa-chevron-right text-xl"></i></div>

            <!-- 右侧小组 -->
            <div class="flex-1 bg-white rounded-xl shadow-lg border border-blue-100 flex flex-col relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-indigo-500"></div>
                <form action="/create_group_submit" method="POST" class="flex flex-col h-full">
                    <div class="p-6 border-b">
                        <label class="block text-sm font-bold text-gray-700 mb-2">小组名称</label>
                        <input name="group_name" type="text" required placeholder="例如: 飞跃队" 
                               value="{{ user.group_name if user.group_name else '' }}"
                               class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none bg-gray-50">
                    </div>

                    <div class="flex-1 p-6 overflow-y-auto">
                        <h3 class="text-xs font-bold text-gray-400 uppercase mb-4">成员列表 (Max 4)</h3>
                        <div id="selectedMembers" class="space-y-3">
                            <!-- 组长 -->
                            <div class="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
                                <div class="flex items-center gap-3">
                                    <div class="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">组长</div>
                                    <div>
                                        <div class="text-sm font-bold text-gray-900">{{ user.name }} (我)</div>
                                        <div class="text-xs text-blue-600">{{ user.class_name }}</div>
                                    </div>
                                </div>
                            </div>
                            <!-- 成员动态添加区 -->
                        </div>
                        <div id="hiddenInputs"></div>
                    </div>

                    <div class="p-6 bg-gray-50 border-t">
                        <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-lg shadow-md transition">
                            确认提交
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
        const MAX_MEMBERS = 4;
        let selectedCount = 1;
        const currentUserId = "{{ user.id }}";

        function addToGroup(id, name, className) {
            if (selectedCount >= MAX_MEMBERS) { alert('小组已满'); return; }
            if (document.getElementById('member-' + id)) return;

            const div = document.createElement('div');
            div.id = 'member-' + id;
            div.className = 'flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg shadow-sm';
            div.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-xs font-bold">${name.slice(-2)}</div>
                    <div><div class="text-sm font-medium text-gray-900">${name}</div><div class="text-xs text-gray-500">${className}</div></div>
                </div>
                <button type="button" onclick="removeFromGroup('${id}')" class="text-red-400 hover:text-red-600"><i class="fas fa-times"></i></button>
            `;

            const input = document.createElement('input');
            input.type = 'hidden'; input.name = 'members'; input.value = id; input.id = 'input-' + id;

            document.getElementById('selectedMembers').appendChild(div);
            document.getElementById('hiddenInputs').appendChild(input);

            const card = document.querySelector(`.student-card[data-id="${id}"]`);
            if(card) card.classList.add('hidden');
            selectedCount++;
        }

        function inviteMember(id) {
            if(!confirm('确定要发送邀请吗？')) return;
            fetch(`/invite_member/${id}`)
                .then(response => response.json())
                .then(data => {
                    if(data.success) alert('邀请已发送');
                    else alert(data.message);
                });
        }

        function removeFromGroup(id) {
            document.getElementById('member-' + id).remove();
            document.getElementById('input-' + id).remove();
            const card = document.querySelector(`.student-card[data-id="${id}"]`);
            if(card) { card.classList.remove('hidden'); filterStudents(); }
            selectedCount--;
        }

        function filterStudents() {
            const searchText = document.getElementById('searchInput').value.toLowerCase();
            const classVal = document.getElementById('classFilter').value;
            const cards = document.querySelectorAll('.student-card');

            cards.forEach(card => {
                if (card.classList.contains('hidden') && document.getElementById('member-' + card.dataset.id)) return;

                const matchSearch = card.dataset.name.includes(searchText) || card.dataset.id.includes(searchText);
                const matchClass = !classVal || card.dataset.class === classVal;

                if (matchSearch && matchClass) card.classList.remove('hidden');
                else card.classList.add('hidden');
            });
        }
    </script>
    {% endblock %}
    """,

    'my_group.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="max-w-4xl mx-auto fade-in">
        <h2 class="text-2xl font-bold mb-6">我的小组信息</h2>
        {% if user.group_name %}
            <div class="bg-white rounded-xl shadow-sm border p-6">
                <div class="flex justify-between items-center border-b pb-4 mb-4">
                    <h3 class="text-xl font-bold text-blue-600">{{ user.group_name }}</h3>
                    <div class="flex items-center gap-3">
                        <span class="bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-bold">已组建</span>
                        {% if user.role == '组长' %}
                        <button onclick="showConfirmDialog('dissolve')" class="text-red-500 hover:text-red-700 text-sm font-bold">解散小组</button>
                        {% else %}
                        <button onclick="showConfirmDialog('leave')" class="text-red-500 hover:text-red-700 text-sm font-bold">退出小组</button>
                        {% endif %}
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                {% for m in members %}
                    <div class="flex items-center p-4 bg-gray-50 rounded-lg border border-gray-100 hover-scale hover:bg-white hover:shadow-md transition-all">
                        <div class="w-12 h-12 rounded-full bg-white border flex items-center justify-center text-lg font-bold text-gray-700 mr-4">
                            {{ m.name[0] }}
                        </div>
                        <div>
                            <p class="font-bold text-gray-900">{{ m.name }} <span class="text-xs text-gray-500 bg-gray-200 px-1 rounded">{{ m.role }}</span></p>
                            <p class="text-sm text-gray-500">{{ m.id }} | {{ m.major }}</p>
                        </div>
                    </div>
                {% endfor %}
                </div>
            </div>
        {% else %}
            <div class="text-center py-20 bg-white rounded-xl shadow-sm">
                <p class="text-gray-500 text-lg">暂无小组</p>
                <div class="mt-6 flex justify-center gap-4">
                    <a href="{{ url_for('create_group') }}" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition">去创建</a>
                    <a href="{{ url_for('view_groups') }}" class="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 transition">加入小组</a>
                </div>
            </div>
        {% endif %}
    </div>

    <!-- 确认对话框 -->
    <div id="confirmDialog" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 transform transition-all scale-95 opacity-0" id="confirmContent">
            <div class="text-center mb-6">
                <div class="w-16 h-16 bg-red-100 rounded-full mx-auto flex items-center justify-center mb-4">
                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl"></i>
                </div>
                <h3 class="text-lg font-bold text-gray-800 mb-2" id="confirmTitle">确认操作</h3>
                <p class="text-sm text-gray-600" id="confirmMessage">确定要执行此操作吗？</p>
            </div>
            <div class="flex justify-center gap-3">
                <button onclick="closeConfirmDialog()" class="px-6 py-2 text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition">取消</button>
                <button id="confirmBtn" class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium transition">确认</button>
            </div>
        </div>
    </div>

    <script>
        function showConfirmDialog(action) {
            const dialog = document.getElementById('confirmDialog');
            const content = document.getElementById('confirmContent');
            const title = document.getElementById('confirmTitle');
            const message = document.getElementById('confirmMessage');
            const confirmBtn = document.getElementById('confirmBtn');
            
            if (action === 'dissolve') {
                title.textContent = '确认解散小组';
                message.textContent = '确定要解散小组吗？所有成员将恢复未组队状态。';
                confirmBtn.onclick = () => window.location.href = "{{ url_for('dissolve_group') }}";
            } else if (action === 'leave') {
                title.textContent = '确认退出小组';
                message.textContent = '确定要退出小组吗？';
                confirmBtn.onclick = () => window.location.href = "{{ url_for('leave_group') }}";
            }
            
            dialog.classList.remove('hidden');
            dialog.classList.add('flex');
            setTimeout(() => {
                content.classList.remove('scale-95', 'opacity-0');
                content.classList.add('scale-100', 'opacity-100');
            }, 10);
        }

        function closeConfirmDialog() {
            const dialog = document.getElementById('confirmDialog');
            const content = document.getElementById('confirmContent');
            content.classList.remove('scale-100', 'opacity-100');
            content.classList.add('scale-95', 'opacity-0');
            setTimeout(() => {
                dialog.classList.remove('flex');
                dialog.classList.add('hidden');
            }, 300);
        }
    </script>
    {% endblock %}
    """,

    'select_tutor.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="h-[calc(100vh-6rem)] flex flex-col gap-4 fade-in">
        <!-- 顶部筛选 -->
        <div class="bg-white p-4 rounded-xl shadow-sm border flex gap-4 items-center">
            <div class="flex items-center gap-2 flex-1">
                <div class="relative flex-1 max-w-md">
                    <input type="text" id="searchInput" onkeyup="filterTutors()" 
                           class="w-full border border-gray-300 rounded-lg pl-10 pr-4 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all" 
                           placeholder="搜索导师姓名、研究方向...">
                    <svg class="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                    </svg>
                </div>
            </div>
            
            <div class="flex items-center gap-2">
                <label class="text-sm font-bold text-gray-700">方向筛选</label>
                <select id="dirFilter" onchange="filterTutors()" class="border border-gray-300 rounded-lg px-3 py-2 text-sm w-40 outline-none focus:border-blue-500 transition-colors">
                    <option value="">全部方向</option>
                    {% for d in directions %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
                </select>
            </div>
            <button onclick="resetFilters()" class="px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors">重置</button>
        </div>

        <div class="flex-1 flex gap-6 min-h-0">
            <!-- 左侧导师列表 -->
            <div class="flex-[2] bg-white rounded-xl shadow-sm border flex flex-col overflow-hidden">
                <div class="overflow-y-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-gray-50 sticky top-0 z-10">
                            <tr>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">教师编号</th>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">姓名</th>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">专业</th>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">方向</th>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">招生限额</th>
                                <th class="p-3 text-xs font-bold text-gray-500 border-b">已招收</th>
                            </tr>
                        </thead>
                        <tbody id="tutorTableBody">
                            {% for t in tutors %}
                            <tr class="hover:bg-blue-50 cursor-pointer border-b last:border-b-0 transition tutor-row group hover-scale" 
                                onclick="selectTutorRow(this, '{{ t.id }}')"
                                data-id="{{ t.id }}" data-name="{{ t.name }}" data-dept="{{ t.dept }}" 
                                data-dir="{{ t.direction }}" data-desc="{{ t.description }}"
                                data-limit="{{ t.limit_num }}" data-current="{{ t.current_num }}">
                                <td class="p-3 text-sm text-gray-600">{{ t.id }}</td>
                                <td class="p-3 text-sm font-bold text-gray-800 group-hover:text-blue-600 transition-colors">{{ t.name }}</td>
                                <td class="p-3 text-sm text-gray-600">{{ t.dept }}</td>
                                <td class="p-3 text-sm text-gray-600">{{ t.direction }}</td>
                                <td class="p-3 text-sm text-gray-600">{{ t.limit_num }}</td>
                                <td class="p-3 text-sm text-gray-600">{{ t.current_num }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    <!-- 无结果提示 -->
                    <div id="noResults" class="hidden flex-col items-center justify-center py-20 text-gray-400">
                        <svg class="w-12 h-12 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <p>未找到匹配的导师</p>
                    </div>
                </div>
            </div>

            <!-- 右侧详情与志愿 -->
            <div class="flex-1 flex flex-col gap-4">
                <!-- 详情卡片 -->
                <div class="bg-white p-6 rounded-xl shadow-sm border flex-1 flex flex-col">
                    <h3 id="detailTitle" class="text-lg font-bold text-blue-600 mb-4 border-b pb-2">请选择导师查看详细信息</h3>
                    
                    <div id="detailContent" class="hidden space-y-4 flex-1 overflow-y-auto">
                        <div class="flex gap-4 mb-4">
                            <div class="flex-1 bg-green-50 rounded-lg p-3 border border-green-100">
                                <div class="text-xs text-green-600 mb-1">招生限额</div>
                                <div class="text-xl font-bold text-green-700" id="detailLimit">-</div>
                            </div>
                            <div class="flex-1 bg-orange-50 rounded-lg p-3 border border-orange-100">
                                <div class="text-xs text-orange-600 mb-1">已招收</div>
                                <div class="text-xl font-bold text-orange-700" id="detailCurrent">-</div>
                            </div>
                        </div>
                        
                        <div>
                            <h4 class="text-sm font-bold text-gray-800 mb-2 flex items-center gap-2">
                                <span class="w-1 h-4 bg-blue-500 rounded-full"></span>
                                导师简介
                            </h4>
                            <p id="tutorDesc" class="text-sm text-gray-600 leading-relaxed bg-gray-50 p-4 rounded-lg"></p>
                        </div>
                    </div>
                    <div id="detailPlaceholder" class="flex-1 flex flex-col items-center justify-center text-gray-400">
                        <svg class="w-16 h-16 mb-4 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                        </svg>
                        <p>点击左侧列表查看详情</p>
                    </div>
                </div>

                <!-- 志愿选择 -->
                <div class="bg-white p-6 rounded-xl shadow-sm border">
                    <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>
                        </svg>
                        志愿选择
                    </h3>
                    <!-- Logo -->
        <div class="mb-8 text-center">
            <h1 class="text-3xl font-bold text-gray-800">学生双选系统</h1>
        </div>            <form method="POST" action="/select_tutor" class="space-y-4">
                        <div class="flex items-center gap-2">
                            <label class="w-20 text-sm font-bold text-gray-700">第一志愿</label>
                            <input name="choice_1" list="tutorsList" class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:border-blue-500 outline-none transition-colors" placeholder="输入导师姓名或ID" value="{{ selection.choice_1 or '' }}">
                        </div>
                        <div class="flex items-center gap-2">
                            <label class="w-20 text-sm font-bold text-gray-700">第二志愿</label>
                            <input name="choice_2" list="tutorsList" class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:border-blue-500 outline-none transition-colors" placeholder="输入导师姓名或ID" value="{{ selection.choice_2 or '' }}">
                        </div>
                        <div class="flex items-center gap-2">
                            <label class="w-20 text-sm font-bold text-gray-700">第三志愿</label>
                            <input name="choice_3" list="tutorsList" class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 focus:bg-white focus:border-blue-500 outline-none transition-colors" placeholder="输入导师姓名或ID" value="{{ selection.choice_3 or '' }}">
                        </div>
                        
                        <datalist id="tutorsList">
                            {% for t in tutors %}
                            <option value="{{ t.id }}">{{ t.name }} ({{ t.dept }})</option>
                            {% endfor %}
                        </datalist>

                        <button type="submit" class="w-full mt-4 bg-blue-600 text-white font-bold py-2.5 rounded-lg hover:bg-blue-700 shadow-lg shadow-blue-500/30 transition-all transform hover:-translate-y-0.5">提交志愿</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script>
        function filterTutors() {
            const searchText = document.getElementById('searchInput').value.toLowerCase();
            const dir = document.getElementById('dirFilter').value;
            const rows = document.querySelectorAll('.tutor-row');
            let hasResults = false;
            
            rows.forEach(row => {
                const name = row.dataset.name.toLowerCase();
                const d = row.dataset.dir;
                const desc = (row.dataset.desc || '').toLowerCase();
                
                const matchesSearch = !searchText || name.includes(searchText) || d.toLowerCase().includes(searchText) || desc.includes(searchText);
                const matchesDir = !dir || d === dir;

                if (matchesSearch && matchesDir) {
                    row.style.display = '';
                    hasResults = true;
                } else {
                    row.style.display = 'none';
                }
            });

            const noResults = document.getElementById('noResults');
            if (hasResults) {
                noResults.classList.add('hidden');
                noResults.classList.remove('flex');
            } else {
                noResults.classList.remove('hidden');
                noResults.classList.add('flex');
            }
        }

        function resetFilters() {
            document.getElementById('searchInput').value = '';
            document.getElementById('dirFilter').value = '';
            filterTutors();
        }

        function selectTutorRow(row, id) {
            // Highlight
            document.querySelectorAll('.tutor-row').forEach(r => r.classList.remove('bg-blue-50', 'border-l-4', 'border-blue-600'));
            row.classList.add('bg-blue-50', 'border-l-4', 'border-blue-600');

            // Update Detail
            document.getElementById('detailTitle').innerText = row.dataset.name + " 导师详情";
            document.getElementById('tutorDesc').innerText = row.dataset.desc || "暂无简介";
            document.getElementById('detailLimit').innerText = row.dataset.limit;
            document.getElementById('detailCurrent').innerText = row.dataset.current;
            
            document.getElementById('detailContent').classList.remove('hidden');
            document.getElementById('detailPlaceholder').classList.add('hidden');
            document.getElementById('detailPlaceholder').classList.remove('flex');
        }
    </script>
    {% endblock %}
    """,
    
    'view_groups.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="h-[calc(100vh-6rem)] flex flex-col fade-in">
        

<h2 class="text-2xl font-bold text-gray-800 mb-4 flex items-center gap-4">
            <span class="w-1.5 h-8 bg-blue-600 rounded-full"></span>
            成功组队 
            <span class="text-base font-normal text-gray-500">{{ groups|length }} 个小组</span>
        </h2>
        
        <div class="flex-1 flex gap-6 min-h-0">
            <!-- 左侧小组列表 -->
            <div class="flex-[2] bg-white rounded-xl shadow-sm border flex flex-col overflow-hidden">
                <table class="w-full text-left border-collapse">
                    <thead class="bg-gray-50 sticky top-0 border-b">
                        <tr>
                            <th class="p-3 text-sm font-bold text-gray-700">小组ID</th>
                            <th class="p-3 text-sm font-bold text-gray-700">小组名称</th>
                            <th class="p-3 text-sm font-bold text-gray-700">组长</th>
                            <th class="p-3 text-sm font-bold text-gray-700">成员数</th>
                            <th class="p-3 text-sm font-bold text-gray-700">状态</th>
                        </tr>
                    </thead>
                    <tbody id="groupTableBody">
                        {% for group in groups %}
                        <tr class="hover:bg-blue-50 cursor-pointer border-b last:border-b-0 transition group-row hover-scale"
                            onclick="showGroupDetail({{ loop.index0 }})" 
                            data-index="{{ loop.index0 }}">
                            <td class="p-3 text-sm">{{ loop.index }}</td>
                            <td class="p-3 text-sm font-bold text-blue-600">{{ group.name }}</td>
                            <td class="p-3 text-sm">{{ group.leader }}</td>
                            <td class="p-3 text-sm">{{ group.count }}/4</td>
                            <td class="p-3 text-sm">
                                <span class="px-2 py-1 rounded text-xs {{ 'bg-green-100 text-green-700' if group.count == 4 else 'bg-gray-100 text-gray-600' }}">
                                    {{ '已满员' if group.count == 4 else '可加入' }}
                                </span>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                
                {% if not groups %}
                <div class="flex-1 flex items-center justify-center text-gray-400">
                    <div class="text-center">
                        <i class="fas fa-users text-4xl mb-2"></i>
                        <p>暂无已组建的小组</p>
                    </div>
                </div>
                {% endif %}
            </div>

            <!-- 右侧小组详情 -->
            <div class="flex-1 flex flex-col">
                <div class="bg-white rounded-xl shadow-sm border p-6 flex-1 flex flex-col" id="groupDetailCard">
                    <div id="noSelection" class="flex-1 flex items-center justify-center text-gray-400">
                        <div class="text-center">
                            <i class="fas fa-user-circle text-6xl mb-4"></i>
                            <p class="text-lg">请选择导师查看详细信息</p>
                            <p class="text-sm mt-2">点击左侧表格查看详细信息</p>
                        </div>
                    </div>
                    
                    <div id="groupDetail" class="hidden flex-1 flex flex-col">
                        <div class="flex items-center justify-center mb-6">
                            <div class="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center text-2xl">
                                <i class="fas fa-user"></i>
                            </div>
                        </div>
                        
                        <div class="mb-6 p-4 bg-gray-50 rounded-lg">
                            <div class="flex justify-between mb-2">
                                <span class="text-sm text-gray-500">组长:</span>
                                <span id="detailLeaderId" class="text-sm font-bold"></span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-500">专业:</span>
                                <span id="detailMajor" class="text-sm font-bold"></span>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h4 class="text-sm font-bold text-gray-700 mb-2"><i class="fas fa-users mr-1"></i> 小组成员:</h4>
                            <div id="membersList" class="space-y-2"></div>
                        </div>
                        
                        <div class="mt-auto pt-4 border-t grid grid-cols-2 gap-3">
                            <button id="joinGroupBtn" class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 text-sm" onclick="joinGroup()">
                                <i class="fas fa-user-plus mr-1"></i> 申请加入小组
                            </button>
                            <button id="leaveGroupBtn" class="hidden px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-sm" onclick="confirmLeaveGroup()">
                                <i class="fas fa-times mr-1"></i> 退出小组
                            </button>
                            <button id="dissolveGroupBtn" class="hidden px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm" onclick="confirmDissolveGroup()">
                                <i class="fas fa-trash-alt mr-1"></i> 解散小组
                            </button>
                            <button id="contactLeaderBtn" class="col-span-2 px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 text-sm">
                                <i class="fas fa-phone mr-1"></i> 联系组长
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const groups = {{ groups|tojson }};
        const myGroupName = "{{ user.group_name if user.group_name else '' }}";
        const myRole = "{{ user.role }}";
        let currentGroupIndex = -1;
        
        function showGroupDetail(index) {
            currentGroupIndex = index;
            // Highlight selected row
            document.querySelectorAll('.group-row').forEach(r => {
                r.classList.remove('bg-blue-100', 'border-l-4', 'border-blue-600');
            });
            event.currentTarget.classList.add('bg-blue-100', 'border-l-4', 'border-blue-600');
            
            // Show detail
            const group = groups[index];
            document.getElementById('noSelection').classList.add('hidden');
            document.getElementById('groupDetail').classList.remove('hidden');
            
            // Populate data
            const leader = group.members.find(m => m.role === '组长');
            document.getElementById('detailLeaderId').textContent = leader.name + ' (' + leader.id + ')';
            document.getElementById('detailMajor').textContent = group.major;
            
            // Members list
            const membersList = document.getElementById('membersList');
            membersList.innerHTML = '';
            group.members.forEach(m => {
                const div = document.createElement('div');
                div.className = 'flex items-center gap-2 text-sm';
                div.innerHTML = `
                    <i class="fas fa-user-circle text-gray-400"></i>
                    <span class="${m.role === '组长' ? 'font-bold' : ''}">` + m.name + (m.role === '组长' ? ' (组长)' : '') + `</span>
                `;
                membersList.appendChild(div);
            });
            
            // Logic for Buttons
            const leaveBtn = document.getElementById('leaveGroupBtn');
            const joinBtn = document.getElementById('joinGroupBtn');
            const dissolveBtn = document.getElementById('dissolveGroupBtn');
            
            // Reset visibility
            leaveBtn.classList.add('hidden');
            joinBtn.classList.add('hidden');
            dissolveBtn.classList.add('hidden');
            
            // If viewing my own group
            if (group.name === myGroupName) {
                if (myRole === '组长') {
                    dissolveBtn.classList.remove('hidden');
                } else {
                    leaveBtn.classList.remove('hidden');
                }
            } else {
                // Viewing other group
                // If I don't have a group, I can join
                if (!myGroupName) {
                    joinBtn.classList.remove('hidden');
                    if (group.count >= 4) {
                        joinBtn.disabled = true;
                        joinBtn.classList.add('opacity-50', 'cursor-not-allowed');
                        joinBtn.innerHTML = '<i class="fas fa-ban mr-1"></i> 小组已满';
                    } else {
                        joinBtn.disabled = false;
                        joinBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                        joinBtn.innerHTML = '<i class="fas fa-user-plus mr-1"></i> 申请加入小组';
                    }
                }
            }

            // Contact leader button
            const contactBtn = document.getElementById('contactLeaderBtn');
            contactBtn.onclick = () => contactLeader(leader.id);
            
            // Hide contact button if I am in this group
            if (group.name === myGroupName) {
                 contactBtn.classList.add('hidden');
            } else {
                 contactBtn.classList.remove('hidden');
            }
        }
        
        function contactLeader(leaderId) {
            if (confirm('确定要联系组长吗？')) {
                fetch('/contact_leader/' + leaderId, {
                    method: 'POST'
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        alert('消息已发送给组长！');
                    } else {
                        alert(data.message || '发送失败');
                    }
                });
            }
        }

        function confirmLeaveGroup() {
            if(confirm('确定要退出当前小组吗？')) {
                window.location.href = "{{ url_for('leave_group') }}";
            }
        }

        function confirmDissolveGroup() {
            if(confirm('确定要解散当前小组吗？此操作不可逆！')) {
                window.location.href = "{{ url_for('dissolve_group') }}";
            }
        }

        function joinGroup() {
            if (currentGroupIndex === -1) return;
            const group = groups[currentGroupIndex];
            if(confirm('确定要申请加入小组 "' + group.name + '" 吗？')) {
                window.location.href = "/join_group/" + encodeURIComponent(group.name);
            }
        }
    </script>
    {% endblock %}
    """,
    
    'messages.html': """
    {% extends "base.html" %}
    {% block content %}
    <div class="h-[calc(100vh-6rem)] flex flex-col fade-in">
        <div class="flex justify-between items-center mb-4">
            <h2 class="text-2xl font-bold text-gray-800">消息通知</h2>
            <div class="text-sm text-gray-500">
                共 <span class="font-bold text-blue-600">{{ messages|length }}</span> 条消息
            </div>
        </div>
        
        <div class="flex-1 flex gap-4 min-h-0">
            <!-- 左侧消息列表 -->
            <div class="w-96 bg-white rounded-xl shadow-sm border flex flex-col overflow-hidden">
                <div class="p-3 border-b bg-gray-50">
                    <div class="relative">
                        <i class="fas fa-search absolute left-3 top-3 text-gray-400 text-sm"></i>
                        <input type="text" id="messageSearch" placeholder="搜索消息..." 
                               onkeyup="filterMessages()"
                               class="w-full pl-10 pr-4 py-2 border rounded-lg text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/10">
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto">
                    {% if messages %}
                    <div id="messageList">
                    {% for msg in messages %}
                    <div class="message-item p-4 border-b hover:bg-blue-50 cursor-pointer transition-colors relative hover-scale"
                         data-msg-id="{{ msg.id }}"
                         data-content="{{ msg.content }}"
                         data-type="{{ msg.type }}"
                         data-status="{{ msg.status }}"
                         data-time="{{ msg.created_at }}"
                         onclick="showMessageDetail({{ loop.index0 }})">
                        <div class="flex items-start gap-3">
                            <!-- 消息类型图标 -->
                            <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0
                                        {% if msg.type == 'invite' %}bg-blue-100 text-blue-600
                                        {% elif msg.type == 'contact' %}bg-green-100 text-green-600
                                        {% else %}bg-gray-100 text-gray-600{% endif %}">
                                {% if msg.type == 'invite' %}
                                <i class="fas fa-user-plus"></i>
                                {% elif msg.type == 'contact' %}
                                <i class="fas fa-phone"></i>
                                {% else %}
                                <i class="fas fa-envelope"></i>
                                {% endif %}
                            </div>
                            
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center justify-between mb-1">
                                    <span class="text-xs font-semibold text-gray-700 uppercase">
                                        {% if msg.type == 'invite' %}组队邀请
                                        {% elif msg.type == 'contact' %}联系请求
                                        {% else %}通知{% endif %}
                                    </span>
                                    {% if msg.status == 'unread' %}
                                    <span class="w-2 h-2 bg-blue-500 rounded-full"></span>
                                    {% endif %}
                                </div>
                                <p class="text-sm text-gray-900 font-medium truncate mb-1">{{ msg.content }}</p>
                                <div class="flex items-center justify-between">
                                    <span class="text-xs text-gray-400">{{ msg.created_at }}</span>
                                    {% if msg.status == 'unread' %}
                                    <span class="text-xs bg-blue-500 text-white px-2 py-0.5 rounded-full">未读</span>
                                    {% else %}
                                    <span class="text-xs text-gray-400">{{ msg.status_text }}</span>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                    </div>
                    {% else %}
                    <div class="flex flex-col items-center justify-center h-full text-gray-400 p-8">
                        <i class="fas fa-inbox text-4xl mb-3 opacity-50"></i>
                        <p class="text-sm">暂无消息</p>
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <!-- 右侧消息详情 -->
            <div class="flex-1 bg-white rounded-xl shadow-sm border flex flex-col overflow-hidden">
                <div id="noMessageSelected" class="flex-1 flex flex-col items-center justify-center text-gray-400">
                    <i class="fas fa-envelope-open-text text-6xl mb-4 opacity-30"></i>
                    <p class="text-lg">选择一条消息查看详情</p>
                </div>
                
                <div id="messageDetail" class="hidden flex-1 flex flex-col">
                    <!-- 详情头部 -->
                    <div class="p-6 border-b bg-gray-50">
                        <div class="flex items-start gap-4">
                            <div id="detailIcon" class="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xl flex-shrink-0">
                                <i class="fas fa-envelope"></i>
                            </div>
                            <div class="flex-1">
                                <div class="flex items-center justify-between mb-2">
                                    <h3 id="detailType" class="text-sm font-bold text-gray-500 uppercase">消息类型</h3>
                                    <span id="detailTime" class="text-xs text-gray-400">时间</span>
                                </div>
                                <p id="detailContent" class="text-lg font-semibold text-gray-900 mb-2"></p>
                                <div id="detailStatus" class="inline-flex items-center gap-2">
                                    <span class="w-2 h-2 bg-blue-500 rounded-full"></span>
                                    <span class="text-sm text-gray-600">状态</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 详情内容 -->
                    <div class="flex-1 p-6 overflow-y-auto">
                        <div class="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-4">
                            <h4 class="text-sm font-bold text-gray-700 mb-2">消息内容</h4>
                            <p id="detailFullContent" class="text-sm text-gray-600"></p>
                        </div>
                        
                        <div class="bg-gray-50 rounded-lg p-4">
                            <h4 class="text-sm font-bold text-gray-700 mb-2">消息详情</h4>
                            <div class="space-y-2 text-sm">
                                <div class="flex justify-between">
                                    <span class="text-gray-500">消息ID:</span>
                                    <span id="detailId" class="text-gray-700 font-mono"></span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-500">消息类型:</span>
                                    <span id="detailTypeText" class="text-gray-700"></span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-500">接收时间:</span>
                                    <span id="detailFullTime" class="text-gray-700"></span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div id="detailActions" class="p-4 border-t bg-gray-50">
                        <!-- 动态插入按钮 -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const messagesData = {{ messages|tojson }};
        
        function showMessageDetail(index) {
            const msg = messagesData[index];
            
            // 高亮选中的消息
            document.querySelectorAll('.message-item').forEach(item => {
                item.classList.remove('bg-blue-50', 'border-l-4', 'border-blue-500');
            });
            event.currentTarget.classList.add('bg-blue-50', 'border-l-4', 'border-blue-500');
            
            // Mark as read if unread
            if (msg.status === 'unread') {
                fetch('/mark_read/' + msg.id, { method: 'POST' })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            // Update UI locally
                            msg.status = 'read';
                            // Remove blue dot from list item
                            const dot = event.currentTarget.querySelector('.bg-blue-500.rounded-full');
                            if(dot) dot.remove();
                            // Update badge text
                            const badge = event.currentTarget.querySelector('.bg-blue-500.text-white');
                            if(badge) {
                                badge.className = 'text-xs text-gray-400';
                                badge.innerText = '已读';
                            }
                            
                            // Update global badge
                            const sidebarBadge = document.getElementById('sidebarBadge');
                            if(sidebarBadge) {
                                let count = parseInt(sidebarBadge.innerText);
                                if(count > 1) {
                                    count--;
                                    sidebarBadge.innerText = count > 99 ? '99+' : count;
                                } else {
                                    sidebarBadge.remove();
                                }
                            }
                            
                            // Update detail view status immediately
                            const statusElement = document.getElementById('detailStatus');
                            statusElement.innerHTML = '<span class="w-2 h-2 bg-gray-400 rounded-full"></span><span class="text-sm text-gray-600">已读</span>';
                        }
                    });
            }
            
            // 显示详情面板
            document.getElementById('noMessageSelected').classList.add('hidden');
            document.getElementById('messageDetail').classList.remove('hidden');
            
            // 设置图标和颜色
            const iconElement = document.getElementById('detailIcon');
            if (msg.type === 'invite') {
                iconElement.className = 'w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xl flex-shrink-0';
                iconElement.innerHTML = '<i class="fas fa-user-plus"></i>';
            } else if (msg.type === 'contact') {
                iconElement.className = 'w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xl flex-shrink-0';
                iconElement.innerHTML = '<i class="fas fa-phone"></i>';
            } else {
                iconElement.className = 'w-12 h-12 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center text-xl flex-shrink-0';
                iconElement.innerHTML = '<i class="fas fa-envelope"></i>';
            }
            
            // 填充详情
            document.getElementById('detailType').textContent = msg.type === 'invite' ? '组队邀请' : (msg.type === 'contact' ? '联系请求' : '通知');
            document.getElementById('detailTime').textContent = msg.created_at;
            document.getElementById('detailContent').textContent = msg.content;
            document.getElementById('detailFullContent').innerText = msg.content; // Use innerText to preserve newlines
            document.getElementById('detailId').textContent = '#' + msg.id;
            document.getElementById('detailTypeText').textContent = msg.type === 'invite' ? '组队邀请' : (msg.type === 'contact' ? '联系请求' : '系统通知');
            document.getElementById('detailFullTime').textContent = msg.created_at;
            
            // 状态显示
            const statusElement = document.getElementById('detailStatus');
            if (msg.status === 'unread') {
                statusElement.innerHTML = '<span class="w-2 h-2 bg-blue-500 rounded-full"></span><span class="text-sm text-blue-600 font-medium">未读</span>';
            } else {
                statusElement.innerHTML = '<span class="w-2 h-2 bg-gray-400 rounded-full"></span><span class="text-sm text-gray-600">' + msg.status_text + '</span>';
            }
            
            // 操作按钮
            const actionsElement = document.getElementById('detailActions');
            if (msg.type === 'invite' && msg.status === 'unread') {
                actionsElement.innerHTML = `
                    <div class="flex gap-3 justify-end">
                        <a href="/handle_invite/${msg.id}/reject" class="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 font-medium transition">拒绝</a>
                        <a href="/handle_invite/${msg.id}/accept" class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium transition">同意</a>
                    </div>
                `;
            } else {
                actionsElement.innerHTML = '<p class="text-sm text-gray-400 text-center">该消息已处理</p>';
            }
        }
        
        function filterMessages() {
            const searchText = document.getElementById('messageSearch').value.toLowerCase();
            const items = document.querySelectorAll('.message-item');
            
            items.forEach(item => {
                const content = item.dataset.content.toLowerCase();
                if (content.includes(searchText)) {
                    item.classList.remove('hidden');
                } else {
                    item.classList.add('hidden');
                }
            });
        }
    </script>
    {% endblock %}
    """
}

app.jinja_loader = DictLoader(TEMPLATES)


# ==========================================
# 3. 路由逻辑
# ==========================================

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/')
def index(): return redirect(url_for('login'))


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        sid = request.form.get('id')
        name = request.form.get('name')
        new_pass = request.form.get('new_password')
        confirm_pass = request.form.get('confirm_password')
        
        if new_pass != confirm_pass:
            flash("两次输入的密码不一致", "error")
            return redirect(url_for('reset_password'))
            
        db = get_db()
        user = db.execute('SELECT * FROM students WHERE id = ? AND name = ?', (sid, name)).fetchone()
        
        if user:
            db.execute('UPDATE students SET password = ? WHERE id = ?', (new_pass, sid))
            db.commit()
            flash("密码重置成功，请登录", "success")
            return redirect(url_for('login'))
        else:
            flash("学号或姓名错误，验证失败", "error")
            return redirect(url_for('reset_password'))
            
    return render_template('reset_password.html')


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            college = request.form.get('college')
            contact = request.form.get('contact')
            # 邮箱暂无字段，暂存 contact 或新增字段，这里假设只更新学院和电话
            db.execute('UPDATE students SET college = ?, contact = ? WHERE id = ?', (college, contact, uid))
            db.commit()
            flash("个人信息更新成功", "success")
            return redirect(url_for('profile'))
            
        elif action == 'change_password':
            old_pass = request.form.get('old_password')
            new_pass = request.form.get('new_password')
            confirm_pass = request.form.get('confirm_password')
            
            if str(user['password']) != old_pass:
                flash("原密码错误", "error")
            elif new_pass != confirm_pass:
                flash("两次输入的新密码不一致", "error")
            else:
                db.execute('UPDATE students SET password = ? WHERE id = ?', (new_pass, uid))
                db.commit()
                flash("密码修改成功，请重新登录", "success")
                return redirect(url_for('logout'))
            
        return redirect(url_for('profile'))
        
        return redirect(url_for('profile'))
        
    # 获取课题和志愿信息
    topic = None
    selection = None
    if user['group_name']:
        topic = db.execute('SELECT * FROM topics WHERE group_name = ?', (user['group_name'],)).fetchone()
        selection = db.execute('SELECT * FROM selections WHERE student_id = ?', (uid,)).fetchone()
        
        # 如果是组员，尝试获取组长的志愿（因为志愿是组长提交的）
        if not selection and user['role'] != '组长':
            leader = db.execute("SELECT id FROM students WHERE group_name = ? AND role = '组长'", (user['group_name'],)).fetchone()
            if leader:
                selection = db.execute('SELECT * FROM selections WHERE student_id = ?', (leader['id'],)).fetchone()

    # 处理志愿显示的导师名字
    selection_display = []
    if selection:
        for i in range(1, 4):
            tid = selection[f'choice_{i}']
            if tid:
                t = db.execute('SELECT name FROM tutors WHERE id = ?', (tid,)).fetchone()
                selection_display.append(f"志愿{i}: {t['name']}" if t else f"志愿{i}: {tid}")
            else:
                selection_display.append(f"志愿{i}: 未选择")
    
    return render_template('profile.html', page='profile', user=dict(user), topic=dict(topic) if topic else None, selection=selection_display)


@app.route('/submit_topic', methods=['GET', 'POST'])
@login_required
def submit_topic():
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    # 权限检查
    if not user['group_name'] or user['role'] != '组长':
        flash("只有组长可以提交课题", "error")
        return redirect(url_for('my_group'))
        
    if request.method == 'POST':
        direction = request.form.get('direction')
        intro = request.form.get('introduction')
        
        # 保存课题
        db.execute('INSERT INTO topics (group_name, direction, introduction) VALUES (?, ?, ?)',
                   (user['group_name'], direction, intro))
                   
        # 通知组员
        members = db.execute('SELECT * FROM students WHERE group_name = ? AND id != ?', 
                             (user['group_name'], uid)).fetchall()
        
        content = f"组长 {user['name']} 已提交课题：{direction}"
        for m in members:
            db.execute('INSERT INTO messages (sender_id, receiver_id, type, content, group_name) VALUES (?, ?, ?, ?, ?)',
                       (uid, m['id'], 'system', content, user['group_name']))
                       
        db.commit()
        flash("课题提交成功，已通知所有组员", "success")
        return redirect(url_for('my_group'))
        
    return render_template('submit_topic.html', page='submit_topic', user=dict(user))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        db = get_db()
        try:
            user = db.execute('SELECT * FROM students WHERE id = ?', (username,)).fetchone()
            if user and str(user['password']) == password:
                session['user_id'] = user['id']
                return redirect(url_for('my_group'))
            flash("账号或密码错误 (默认123456)", "error")
        except Exception as e:
            flash(f"错误: {e}", "error")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.context_processor
def inject_user():
    if 'user_id' in session:
        db = get_db()
        user = db.execute('SELECT * FROM students WHERE id = ?', (session['user_id'],)).fetchone()
        if user:
            unread_count = db.execute("SELECT count(*) FROM messages WHERE receiver_id = ? AND status = 'unread'", (session['user_id'],)).fetchone()[0]
            return dict(user=dict(user), unread_count=unread_count)
    return dict(user=None, unread_count=0)


@app.route('/create_group')
@login_required
def create_group():
    db = get_db()
    uid = session['user_id']

    # 1. 获取当前用户的信息，主要是专业
    me = db.execute('SELECT major, group_name FROM students WHERE id = ?', (uid,)).fetchone()

    # 检查是否已组队
    if me['group_name']:
        flash("你已经加入小组，无法创建新组。请先退出当前小组。", "error")
        return redirect(url_for('my_group'))

    # 如果用户数据未加载（可能CSV导入失败，只有测试数据），则使用默认测试专业
    my_major = me['major'] if me and me['major'] else '信息管理与信息系统'

    # 2. 核心逻辑：只查询 同专业 且 未组队 的学生
    query = '''
        SELECT * FROM students 
        WHERE (group_name IS NULL OR group_name = '') 
        AND id != ?
        AND major = ?
        ORDER BY class_name, id
    '''
    students = db.execute(query, (uid, my_major)).fetchall()

    # 3. 获取同专业的班级列表用于筛选
    classes = db.execute('''
        SELECT DISTINCT class_name FROM students 
        WHERE major = ? AND class_name IS NOT NULL
        ORDER BY class_name
    ''', (my_major,)).fetchall()

    return render_template('create_group.html',
                           page='create_group',
                           students=[dict(s) for s in students],
                           classes=[c['class_name'] for c in classes])


@app.route('/create_group_submit', methods=['POST'])
@login_required
def create_group_submit():
    db = get_db()
    uid = session['user_id']
    group_name = request.form.get('group_name')
    mids = request.form.getlist('members')

    if not group_name:
        flash("请输入小组名称", "error")
        return redirect(url_for('create_group'))

    if len(mids) + 1 > 4:
        flash("小组人数最多为4人（包括组长）", "error")
        return redirect(url_for('create_group'))

    try:
        # 更新自己
        db.execute("UPDATE students SET group_name = ?, role = '组长' WHERE id = ?", (group_name, uid))
        # 更新队员
        for mid in mids:
            check = db.execute('SELECT group_name FROM students WHERE id = ?', (mid,)).fetchone()
            if check and check['group_name'] and check['group_name'] != group_name:
                continue  # 已有组则跳过
            db.execute("UPDATE students SET group_name = ?, role = '成员' WHERE id = ?", (group_name, mid))
        db.commit()
        flash("小组操作成功！", "success")
        return redirect(url_for('my_group'))
    except Exception as e:
        db.rollback()
        flash(f"操作失败: {e}", "error")
        return redirect(url_for('create_group'))


@app.route('/my_group')
@login_required
def my_group():
    db = get_db()
    user = db.execute('SELECT * FROM students WHERE id = ?', (session['user_id'],)).fetchone()
    members = []
    if user['group_name']:
        members = db.execute('SELECT * FROM students WHERE group_name = ?', (user['group_name'],)).fetchall()
    return render_template('my_group.html', page='my_group', members=[dict(m) for m in members])


@app.route('/dissolve_group')
@login_required
def dissolve_group():
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    if user and user['role'] == '组长' and user['group_name']:
        # 解散小组：所有成员重置
        db.execute("UPDATE students SET group_name = NULL, role = '成员' WHERE group_name = ?", (user['group_name'],))
        db.commit()
        flash("小组已解散", "success")
    else:
        flash("无权操作或未组队", "error")
    
    return redirect(url_for('my_group'))


@app.route('/contact_leader/<leader_id>', methods=['POST'])
@login_required
def contact_leader(leader_id):
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    # 发送消息给组长
    content = f"组员 {user['name']} ({user['id']}) 想要联系您"
    db.execute('INSERT INTO messages (sender_id, receiver_id, type, content) VALUES (?, ?, ?, ?)',
               (uid, leader_id, 'system', content))
    db.commit()
    
    return {'success': True, 'message': '消息已发送'}


@app.route('/leave_group')
@login_required
def leave_group():
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    if user and user['group_name'] and user['role'] != '组长':
        db.execute("UPDATE students SET group_name = NULL WHERE id = ?", (uid,))
        db.commit()
        flash("已退出小组", "success")
    else:
        flash("组长无法直接退出，请选择解散小组", "error")
    
    return redirect(url_for('my_group'))


@app.route('/view_groups')
@login_required
def view_groups():
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    
    # 查询所有有小组的学生
    rows = db.execute('''
        SELECT * FROM students 
        WHERE group_name IS NOT NULL AND group_name != ''
        ORDER BY group_name, role DESC
    ''').fetchall()
    
    # 整理数据结构
    groups_map = {}
    for row in rows:
        gname = row['group_name']
        if gname not in groups_map:
            groups_map[gname] = {
                'name': gname,
                'major': row['major'],
                'leader': '',
                'members': [],
                'count': 0
            }
        
        groups_map[gname]['members'].append(dict(row))
        groups_map[gname]['count'] += 1
        if row['role'] == '组长':
            groups_map[gname]['leader'] = row['name']
            
    return render_template('view_groups.html', page='view_groups', groups=list(groups_map.values()))


@app.route('/join_group/<group_name>')
@login_required
def join_group(group_name):
    db = get_db()
    uid = session['user_id']
    
    # 检查用户状态
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    if user['group_name']:
        flash("你已经有小组了，无法加入其他小组。请先退出当前小组。", "error")
        return redirect(url_for('view_groups'))
        
    # 检查小组状态
    members = db.execute('SELECT * FROM students WHERE group_name = ?', (group_name,)).fetchall()
    if not members:
        flash("小组不存在", "error")
        return redirect(url_for('view_groups'))
        
    if len(members) >= 4:
        flash("该小组已满员", "error")
        return redirect(url_for('view_groups'))
        
    # 检查专业是否一致 (可选，根据需求，通常同专业组队)
    if user['major'] != members[0]['major']:
        flash("只能加入同专业的小组", "error")
        return redirect(url_for('view_groups'))
        
    # 加入
    db.execute("UPDATE students SET group_name = ?, role = '成员' WHERE id = ?", (group_name, uid))
    db.commit()
    flash(f"成功加入小组 {group_name}", "success")
    return redirect(url_for('my_group'))


@app.route('/messages')
@login_required
def messages():
    db = get_db()
    uid = session['user_id']
    
    msgs = db.execute('''
        SELECT * FROM messages 
        WHERE receiver_id = ? 
        ORDER BY created_at DESC
    ''', (uid,)).fetchall()
    
    # 处理显示文本
    formatted_msgs = []
    for m in msgs:
        m = dict(m)
        if m['status'] == 'unread': m['status_text'] = '未读'
        elif m['status'] == 'accepted': m['status_text'] = '已同意'
        elif m['status'] == 'rejected': m['status_text'] = '已拒绝'
        else: m['status_text'] = '已读'
        formatted_msgs.append(m)
        
    return render_template('messages.html', page='messages', messages=formatted_msgs)


@app.route('/invite_member/<student_id>')
@login_required
def invite_member(student_id):
    db = get_db()
    uid = session['user_id']
    
    # 检查权限
    me = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    if not me['group_name'] or me['role'] != '组长':
        return {'success': False, 'message': '只有组长才能邀请'}
        
    # 检查小组人数
    count = db.execute('SELECT count(*) FROM students WHERE group_name = ?', (me['group_name'],)).fetchone()[0]
    if count >= 4:
        return {'success': False, 'message': '小组已满'}
        
    # 检查目标
    target = db.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    if target['group_name']:
        return {'success': False, 'message': '对方已有小组'}
        
    # 发送邀请
    content = f"收到来自 {me['name']} ({me['group_name']}) 的入组邀请"
    db.execute('''
        INSERT INTO messages (sender_id, receiver_id, type, content, group_name)
        VALUES (?, ?, 'invite', ?, ?)
    ''', (uid, student_id, content, me['group_name']))
    db.commit()
    
    return {'success': True}


@app.route('/handle_invite/<int:msg_id>/<action>')
@login_required
def handle_invite(msg_id, action):
    db = get_db()
    uid = session['user_id']
    
    msg = db.execute('SELECT * FROM messages WHERE id = ?', (msg_id,)).fetchone()
    if not msg or msg['receiver_id'] != uid:
        flash("消息不存在", "error")
        return redirect(url_for('messages'))
        
    if msg['status'] != 'unread':
        flash("该邀请已处理", "error")
        return redirect(url_for('messages'))
        
    if action == 'accept':
        # 检查自己是否已有组
        me = db.execute('SELECT group_name FROM students WHERE id = ?', (uid,)).fetchone()
        if me['group_name']:
            flash("你已有小组，无法接受邀请", "error")
            return redirect(url_for('messages'))
            
        # 检查目标小组是否已满
        count = db.execute('SELECT count(*) FROM students WHERE group_name = ?', (msg['group_name'],)).fetchone()[0]
        if count >= 4:
            flash("目标小组已满", "error")
            return redirect(url_for('messages'))
            
        # 加入小组
        db.execute("UPDATE students SET group_name = ?, role = '成员' WHERE id = ?", (msg['group_name'], uid))
        db.execute("UPDATE messages SET status = 'accepted' WHERE id = ?", (msg_id,))
        flash(f"成功加入小组 {msg['group_name']}", "success")
        
    elif action == 'reject':
        db.execute("UPDATE messages SET status = 'rejected' WHERE id = ?", (msg_id,))
        flash("已拒绝邀请", "success")
        
    db.commit()
    return redirect(url_for('messages'))


@app.route('/mark_read/<int:msg_id>', methods=['POST'])
@login_required
def mark_read(msg_id):
    db = get_db()
    uid = session['user_id']
    
    # 验证消息属于当前用户
    msg = db.execute('SELECT * FROM messages WHERE id = ? AND receiver_id = ?', (msg_id, uid)).fetchone()
    if msg:
        db.execute("UPDATE messages SET status = 'read' WHERE id = ?", (msg_id,))
        db.commit()
        return {'success': True}
    return {'success': False, 'message': 'Message not found or permission denied'}


@app.route('/select_tutor', methods=['GET', 'POST'])
@login_required
def select_tutor():
    db = get_db()
    uid = session['user_id']
    
    # 权限检查：只有组长能选导师
    user = db.execute('SELECT * FROM students WHERE id = ?', (uid,)).fetchone()
    if not user['group_name'] or user['role'] != '组长':
        flash("只有组长可以进行导师选择", "error")
        return redirect(url_for('my_group'))
    
    if request.method == 'POST':
        c1 = request.form.get('choice_1')
        c2 = request.form.get('choice_2')
        c3 = request.form.get('choice_3')
        
        # 简单验证：不能重复选择同一导师
        choices = [c for c in [c1, c2, c3] if c]
        if len(choices) != len(set(choices)):
            flash("不能重复选择同一位导师", "error")
        else:
            db.execute('INSERT OR REPLACE INTO selections (student_id, choice_1, choice_2, choice_3) VALUES (?, ?, ?, ?)',
                       (uid, c1, c2, c3))
                       
            # 通知组员
            members = db.execute('SELECT * FROM students WHERE group_name = ? AND id != ?', 
                                 (user['group_name'], uid)).fetchall()
            
            # 获取导师名字
            tutor_names = []
            for tid in [c1, c2, c3]:
                if tid:
                    t = db.execute('SELECT name FROM tutors WHERE id = ?', (tid,)).fetchone()
                    tutor_names.append(f"{t['name']}({tid})" if t else tid)
                else:
                    tutor_names.append("未选择")
            
            content = f"组长 {user['name']} 已提交/更新导师志愿：\n1. {tutor_names[0]}\n2. {tutor_names[1]}\n3. {tutor_names[2]}"
            for m in members:
                db.execute('INSERT INTO messages (sender_id, receiver_id, type, content, group_name) VALUES (?, ?, ?, ?, ?)',
                           (uid, m['id'], 'system', content, user['group_name']))
                           
            db.commit()
            flash("志愿提交成功，已通知所有组员", "success")
        return redirect(url_for('select_tutor'))

    # 获取所有导师
    tutors = db.execute('SELECT * FROM tutors').fetchall()
    
    # 获取当前志愿
    selection = db.execute('SELECT * FROM selections WHERE student_id = ?', (uid,)).fetchone()
    
    # 获取专业和方向列表用于筛选
    majors = sorted(list(set(t['dept'] for t in tutors if t['dept'])))
    directions = sorted(list(set(t['direction'] for t in tutors if t['direction'])))
    
    return render_template('select_tutor.html', 
                           page='select_tutor', 
                           tutors=[dict(t) for t in tutors],
                           selection=dict(selection) if selection else {},
                           majors=majors,
                           directions=directions)


# 启动初始化
init_db()

if __name__ == '__main__':
    print("启动系统...")
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=True)