import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict

load_dotenv()

class Config(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8442093912:AAEZv5LHx0_Yi_2LlZUl7YD-PTH6XMD72gs")
    ADMINS: List[int] = Field(default_factory=list)
    XUI_API_URL: str = os.getenv("XUI_API_URL", "http://85.192.26.36:8080/eWaOoqgUCezndPKXkz")
    XUI_BASE_PATH: str = os.getenv("XUI_BASE_PATH", "/panel")
    XUI_USERNAME: str = os.getenv("XUI_USERNAME", "Nck4vyaD6R")
    XUI_PASSWORD: str = os.getenv("XUI_PASSWORD", "uIQ1pwQWFU")
    XUI_HOST: str = os.getenv("XUI_HOST", "85.192.26.36")
    XUI_SERVER_NAME: str = os.getenv("XUI_SERVER_NAME", "web.max.ru")
    PAYMENT_TOKEN: str = os.getenv("PAYMENT_TOKEN", "")
    INBOUND_ID: int = Field(default=os.getenv("INBOUND_ID", 1))
    REALITY_PUBLIC_KEY: str = os.getenv("REALITY_PUBLIC_KEY", "N0aZfOysFpwQ2tAI6uNaSbSpmBdGngSurOJgmRtEOAA")
    REALITY_FINGERPRINT: str = os.getenv("REALITY_FINGERPRINT", "chrome")
    REALITY_SNI: str = os.getenv("REALITY_SNI", "web.max.ru")
    REALITY_SHORT_ID: str = os.getenv("REALITY_SHORT_ID", "9beb73f8b919bac8")
    REALITY_SPIDER_X: str = os.getenv("REALITY_SPIDER_X", "/")

    # Настройки цен и скидок
    PRICES: Dict[int, Dict[str, int]] = {
        1: {"base_price": 250, "discount_percent": 0},
        3: {"base_price": 750, "discount_percent": 10},
        6: {"base_price": 1500, "discount_percent": 20},
        12: {"base_price": 3000, "discount_percent": 30}
    }

    @field_validator('ADMINS', mode='before')
    def parse_admins(cls, value):
        if isinstance(value, str):
            return [int(admin) for admin in value.split(",") if admin.strip()]
        return value or []
    
    @field_validator('INBOUND_ID', mode='before')
    def parse_inbound_id(cls, value):
        if isinstance(value, str):
            return int(value)
        return value or 1
    
    def calculate_price(self, months: int) -> int:
        """Вычисляет итоговую стоимость с учетом скидки"""
        if months not in self.PRICES:
            return 0
        
        price_info = self.PRICES[months]
        base_price = price_info["base_price"]
        discount_percent = price_info["discount_percent"]
        
        discount_amount = (base_price * discount_percent) // 100
        return base_price - discount_amount

config = Config(
    ADMINS="7569139197",
    INBOUND_ID=1
)
