#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Authenticator
# =============================================================================
class Authenticator:
    def __init__(self):
        load_dotenv() 
        self.username = os.getenv('USERNAME')
        self.password = os.getenv('PASSWORD')
        if not self.username or not self.password:
            raise ValueError("請在 .env 檔案中設定 USERNAME 與 PASSWORD 環境變數。")
        self.session = requests.Session()
        self.session.headers.update({'Referer': 'https://iclass.tku.edu.tw/'})
        self.auth_url = (
            "https://sso.tku.edu.tw/auth/realms/TKU/protocol/openid-connect/auth"
            "?client_id=pdsiclass&response_type=code&redirect_uri=https%3A//iclass.tku.edu.tw/login"
            "&state=L2lwb3J0YWw=&scope=openid,public_profile,email"
        )
    
    def perform_auth(self):
        try:
            self.session.get("https://iclass.tku.edu.tw/login?next=/iportal&locale=zh_TW")
            self.session.get(self.auth_url)
            login_page_url = f"https://sso.tku.edu.tw/NEAI/logineb.jsp?myurl={self.auth_url}"
            login_page = self.session.get(login_page_url)
            jsessionid = login_page.cookies.get("AMWEBJCT!%2FNEAI!JSESSIONID")
            if not jsessionid:
                raise ValueError("無法取得 JSESSIONID")
            
            image_headers = {
                'Referer': 'https://sso.tku.edu.tw/NEAI/logineb.jsp',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            }
            self.session.get("https://sso.tku.edu.tw/NEAI/ImageValidate", headers=image_headers)
            post_headers = {
                'Origin': 'https://sso.tku.edu.tw',
                'Referer': 'https://sso.tku.edu.tw/NEAI/logineb.jsp'
            }
            body = {'outType': '2'}
            response = self.session.post("https://sso.tku.edu.tw/NEAI/ImageValidate", headers=post_headers, data=body)
            vidcode = response.text.strip()
            
            payload = {
                "myurl": self.auth_url,
                "ln": "zh_TW",
                "embed": "No",
                "vkb": "No",
                "logintype": "logineb",
                "username": self.username,
                "password": self.password,
                "vidcode": vidcode,
                "loginbtn": "登入"
            }
            login_url = f"https://sso.tku.edu.tw/NEAI/login2.do;jsessionid={jsessionid}?action=EAI"
            self.session.post(login_url, data=payload)
            
            headers = {'Referer': login_url, 'Upgrade-Insecure-Requests': '1'}
            user_redirect_url = (
                f"https://sso.tku.edu.tw/NEAI/eaido.jsp?"
                f"am-eai-user-id={self.username}&am-eai-redir-url={self.auth_url}"
            )
            self.session.get(user_redirect_url, headers=headers)
            
            return self.session
        except requests.exceptions.RequestException as e:
            raise Exception("Authentication failed: " + str(e))

# =============================================================================
# TronClassAPI
# =============================================================================
class TronClassAPI:
    def __init__(self, session):
        self.session = session

    async def get_todos(self):
        todos_url = "https://iclass.tku.edu.tw/api/todos"
        try:
            response = self.session.get(todos_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching todos: {str(e)}"}
    
    async def get_bulletins(self):
        url = "https://iclass.tku.edu.tw/api/course-bulletins"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching bulletins: {str(e)}"}

    async def get_courses(self):
        url = 'https://iclass.tku.edu.tw/api/my-courses?conditions=%7B%22status%22:%5B%22ongoing%22%5D,%22keyword%22:%22%22,%22classify_type%22:%22recently_started%22,%22display_studio_list%22:false%7D&fields=id,name,course_code,department(id,name),grade(id,name),klass(id,name),course_type,cover,small_cover,start_date,end_date,is_started,is_closed,academic_year_id,semester_id,credit,compulsory,second_name,display_name,created_user(id,name),org(is_enterprise_or_organization),org_id,public_scope,audit_status,audit_remark,can_withdraw_course,imported_from,allow_clone,is_instructor,is_team_teaching,is_default_course_cover,archived,instructors(id,name,email,avatar_small_url),course_attributes(teaching_class_name,is_during_publish_period,passing_score,score_type,copy_status,tip,data,graduate_method),user_stick_course_record(id)&page=1&page_size=10&showScorePassedStatus=true?'
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching courses: {str(e)}"}

    async def upload_file(self,file_path:str):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        metadata_url = "https://iclass.tku.edu.tw/api/uploads"

        headers_metadata = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://iclass.tku.edu.tw",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)..."
        }

        metadata_payload = {
            "name": file_name,
            "size": file_size,
            "parent_type": None,
            "parent_id": 0,
            "is_scorm": False,
            "is_wmpkg": False,
            "source": "",
            "is_marked_attachment": False,
            "embed_material_type": ""
        }
        response_metadata = self.session.post(
            metadata_url,
            headers=headers_metadata,
            data=json.dumps(metadata_payload)
        )

        if response_metadata.status_code != 201:
            print("❌ Failed to get upload URL")
            print(response_metadata.status_code, response_metadata.text)
            return {"error":f"Failed to get upload URL, status_code:{response_metadata.status_code}"}

        upload_info = response_metadata.json()
        upload_url = upload_info["upload_url"]
        upload_file_name = upload_info["name"]
        upload_file_id = upload_info["id"]
        upload_file_type = upload_info["type"]

        print(f"✅ Got upload URL:\n{upload_url}")

        with open(file_path, 'rb') as f:
            files = {
                'file': (upload_file_name, f, upload_file_type)
            }
            headers_upload = {
                "Origin": "https://iclass.tku.edu.tw",
                "Referer": "https://iclass.tku.edu.tw/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)..."
            }

            upload_response = self.session.put(upload_url, files=files, headers=headers_upload)

            print(f"📤 Upload response: {upload_response.status_code}")
            print(upload_response.text)
            print(f"Upload file id {upload_file_id}")
        return upload_file_id
    
    async def submit_homework(self, activity_id, upload_ids:list):
        url = f'https://iclass.tku.edu.tw/api/course/activities/{activity_id}/submissions'

        headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/json;charset=UTF-8',
        'origin': 'https://iclass.tku.edu.tw',
        }

        payload = {
            "comment": "",
            "uploads": upload_ids,  # List of uploaded file IDs
            "slides": [],
            "is_draft": False,
            "mode": "normal",
            "other_resources": [],
            "uploads_in_rich_text": []
        }

        response = self.session.post(url, headers=headers, data=json.dumps(payload))

        if response.ok:
            return {"Submission successful",response.status_code, response.text}
        else:
            return {"Submission failed", response.status_code, response.text}

# =============================================================================
# MCP Server
# =============================================================================
mcp = FastMCP(
    "TKU-MCP",
    description="TronClass and TKU-ilife integration through the Model Context Protocol",
)

@mcp.tool()
async def getToDo():
    """
    Get the list of todos from TronClass
    """
    try:
        auth = Authenticator()
        session = auth.perform_auth()
        api = TronClassAPI(session)
        todos = await api.get_todos()
        return todos
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def getBulletins():
    """
    Get the list of bulletins from TronClass
    """
    try:
        auth = Authenticator()
        session = auth.perform_auth()
        api = TronClassAPI(session)
        bulletins = await api.get_bulletins()
        return bulletins
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def getCourses():
    """
    Get the list of courses from TronClass
    """
    try:
        auth = Authenticator()
        session = auth.perform_auth()
        api = TronClassAPI(session)
        courses = await api.get_courses()
        return courses
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
