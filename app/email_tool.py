import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Dict, Any, List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .models import Tool

logger = logging.getLogger(__name__)

class EmailTool:
    """Email tool for AI agents to send emails"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def _send_email_sync(self, 
                        smtp_server: str,
                        smtp_port: int,
                        username: str,
                        password: str,
                        from_email: str,
                        to_emails: List[str],
                        subject: str,
                        body: str,
                        html_body: str = None,
                        attachments: List[str] = None,
                        use_tls: bool = True) -> Dict[str, Any]:
        """Synchronous email sending function"""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = from_email
            message["To"] = ", ".join(to_emails)
            message["Subject"] = subject
            
            # Add text body
            text_part = MIMEText(body, "plain", "utf-8")
            message.attach(text_part)
            
            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                message.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                        
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        message.attach(part)
            
            # Create SMTP session
            if use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            
            # Login and send email
            server.login(username, password)
            text = message.as_string()
            server.sendmail(from_email, to_emails, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return {
                "success": True,
                "message": f"Email sent to {len(to_emails)} recipient(s)",
                "recipients": to_emails
            }
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def send_email(self,
                        smtp_config: Dict[str, Any],
                        to_emails: List[str],
                        subject: str,
                        body: str,
                        html_body: str = None,
                        attachments: List[str] = None) -> Dict[str, Any]:
        """Send email asynchronously"""
        try:
            # Extract SMTP configuration
            smtp_server = smtp_config.get("smtp_server")
            smtp_port = smtp_config.get("smtp_port", 587)
            username = smtp_config.get("username")
            password = smtp_config.get("password")
            from_email = smtp_config.get("from_email", username)
            use_tls = smtp_config.get("use_tls", True)
            
            # Validate required fields
            if not all([smtp_server, username, password]):
                return {
                    "success": False,
                    "error": "Missing required SMTP configuration: smtp_server, username, password"
                }
            
            if not to_emails:
                return {"success": False, "error": "No recipients specified"}
            
            # Ensure to_emails is a list
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            
            # Run email sending in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._send_email_sync,
                smtp_server,
                smtp_port,
                username,
                password,
                from_email,
                to_emails,
                subject,
                body,
                html_body,
                attachments,
                use_tls
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in send_email: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def send_template_email(self,
                                smtp_config: Dict[str, Any],
                                to_emails: List[str],
                                template_name: str,
                                template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using a template"""
        try:
            # Define email templates
            templates = {
                "welcome": {
                    "subject": "Hoş Geldiniz! - {agent_name}",
                    "body": """
Merhaba {user_name},

{agent_name} AI asistanına hoş geldiniz! 

Bu e-posta, zamanlanmış görevlerinizin başarıyla oluşturulduğunu bildirmek için gönderildi.

Saygılarımla,
{agent_name}
                    """,
                    "html_body": """
<html>
<body>
    <h2>Merhaba {user_name},</h2>
    <p><strong>{agent_name}</strong> AI asistanına hoş geldiniz!</p>
    <p>Bu e-posta, zamanlanmış görevlerinizin başarıyla oluşturulduğunu bildirmek için gönderildi.</p>
    <br>
    <p>Saygılarımla,<br><strong>{agent_name}</strong></p>
</body>
</html>
                    """
                },
                "reminder": {
                    "subject": "Hatırlatma - {subject}",
                    "body": """
Merhaba {user_name},

Bu bir hatırlatma mesajıdır:

{message}

Tarih: {date}

Saygılarımla,
{agent_name}
                    """,
                    "html_body": """
<html>
<body>
    <h2>Hatırlatma</h2>
    <p>Merhaba <strong>{user_name}</strong>,</p>
    <p>Bu bir hatırlatma mesajıdır:</p>
    <div style="background-color: #f0f8ff; padding: 15px; border-left: 4px solid #007bff;">
        {message}
    </div>
    <p><strong>Tarih:</strong> {date}</p>
    <br>
    <p>Saygılarımla,<br><strong>{agent_name}</strong></p>
</body>
</html>
                    """
                },
                "report": {
                    "subject": "Rapor - {report_title}",
                    "body": """
Merhaba {user_name},

{report_title} raporu hazır:

{report_content}

Bu rapor {date} tarihinde oluşturulmuştur.

Saygılarımla,
{agent_name}
                    """,
                    "html_body": """
<html>
<body>
    <h2>{report_title}</h2>
    <p>Merhaba <strong>{user_name}</strong>,</p>
    <div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6;">
        {report_content}
    </div>
    <p><small>Bu rapor {date} tarihinde oluşturulmuştur.</small></p>
    <br>
    <p>Saygılarımla,<br><strong>{agent_name}</strong></p>
</body>
</html>
                    """
                }
            }
            
            template = templates.get(template_name)
            if not template:
                return {"success": False, "error": f"Template '{template_name}' not found"}
            
            # Format template with data
            subject = template["subject"].format(**template_data)
            body = template["body"].format(**template_data)
            html_body = template["html_body"].format(**template_data)
            
            # Send email
            return await self.send_email(
                smtp_config=smtp_config,
                to_emails=to_emails,
                subject=subject,
                body=body,
                html_body=html_body
            )
            
        except Exception as e:
            logger.error(f"Error sending template email: {str(e)}")
            return {"success": False, "error": str(e)}

# Global email tool instance
email_tool = EmailTool()

# Tool execution function for integration with tool_executor
async def execute_email_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Email tool to send emails.
    
    Args:
        tool: The Email tool configuration
        params: Parameters containing email details
    
    Returns:
        Dict containing the result of the email sending
    """
    try:
        # Get SMTP configuration from tool config or environment
        smtp_config = tool.config.copy() if tool.config else {}
        
        # Override with environment variables if available
        env_config = {
            "smtp_server": os.getenv("SMTP_SERVER"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME"),
            "password": os.getenv("SMTP_PASSWORD"),
            "from_email": os.getenv("SMTP_FROM_EMAIL"),
            "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        }
        
        # Update config with non-None environment values
        for key, value in env_config.items():
            if value is not None:
                smtp_config[key] = value
        
        # Get email parameters
        to_emails = params.get("to")
        subject = params.get("subject", "Mesaj")
        body = params.get("body", "")
        html_body = params.get("html_body")
        template_name = params.get("template")
        template_data = params.get("template_data", {})
        attachments = params.get("attachments", [])
        
        if not to_emails:
            return {"success": False, "error": "No recipients specified"}
        
        # Send template email if template is specified
        if template_name:
            result = await email_tool.send_template_email(
                smtp_config=smtp_config,
                to_emails=to_emails,
                template_name=template_name,
                template_data=template_data
            )
        else:
            # Send regular email
            result = await email_tool.send_email(
                smtp_config=smtp_config,
                to_emails=to_emails,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=attachments
            )
        
        logger.info(f"Email tool {tool.toolId} executed: {result.get('success', False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in email tool {tool.toolId}: {str(e)}")
        return {"success": False, "error": str(e)}
