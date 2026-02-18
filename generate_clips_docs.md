
Запрос на создание коротких кдипов из видео
https://api.opus.pro/api/clip-projects


POST
201 Created
Payload JSON:
{
    "videoUrl": "https://youtu.be/ZeIFBdoOZXo?si=qQEkg-fA3xT4vgfj",
    "utm": {
        "source": "chatgpt.com"
    },
    "importPref": {
        "sourceLang": "ru"
    },
    "curationPref": {
        "model": "Auto",
        "range": {
            "startSec": 0,
            "endSec": 187
        },
        "clipDurations": [
            [
                0,
                30
            ]
        ],
        "topicKeywords": [],
        "skipSlicing": false,
        "skipCurate": false,
        "genre": "Auto",
        "customPrompt": "найди лучшие моменты клипа",
        "enableAutoHook": true
    },
    "renderPref": {
        "layoutAspectRatio": "portrait"
    },
    "brandTemplateId": "preset-fancy-Karaoke"
}

Заголовки Request:
accept
*/*
accept-encoding
gzip, deflate, br, zstd
accept-language
en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7
authorization
Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Im9wdXMifQ.eyJpc3MiOiJodHRwczovL2FwaS53b3Jrb3MuY29tIiwic3ViIjoidXNlcl8wMUtIRTZXWTdUM1RXRTdRVDlHNjZHWkU4QyIsInNpZCI6InNlc3Npb25fMDFLSEU2V1lEQzZQUjhNQ1c5SDY3TUc1MkYiLCJqdGkiOiIwMUtIRTZXWUZZMjFNREExRVFKSzJNUDdRWCIsImV4cCI6MTc3MTA3NzU3MCwiaWF0IjoxNzcxMDc3MjcwLCJlbWFpbCI6ImNoZWxsYTA1YW5kcmV5QGdtYWlsLmNvbSIsInVzZXJfaWQiOiJ1c2VyXzAxS0hFNldZN1QzVFdFN1FUOUc2NkdaRThDIiwibmFtZSI6ItCQ0L3QtNGA0LXQuSDQp9C10LvQu9CwIiwiZ2l2ZW5fbmFtZSI6ItCQ0L3QtNGA0LXQuSIsImZhbWlseV9uYW1lIjoi0KfQtdC70LvQsCIsIm5pY2tuYW1lIjoi0JDQvdC00YDQtdC5LtCn0LXQu9C70LAiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiY3JlYXRlZF9hdCI6IjIwMjYtMDItMTRUMTM6NTQ6MjkuNzE2WiIsInVwZGF0ZWRfYXQiOiIyMDI2LTAyLTE0VDEzOjU0OjI5LjcxNloiLCJwaWN0dXJlIjoiaHR0cHM6Ly93b3Jrb3NjZG4uY29tL2ltYWdlcy92MS9sTElTa0tsaWpRMldyRkhEd3ZBbV9tM0FFRjE3YVVtVjNjcW9ZUC1aWk9jIiwiYXV0aF90aW1lIjoiMjAyNi0wMi0xNFQxMzo1NDozMC4wOTZaIn0.WyUxvbQdX3IdFux4M57QsU562gwXL52JqHDFgvqSV43N10e3ixPejcOLluAvpW4SmslG7X0wTltZIARHEz7dSEFsdvhqz2rthJhxHhojTlbQAsOn0770afEbJbitDKwVmgofgCghQBiYin6lwyKuS_zJCJ19MFUjApThvl5EWHmKC6i8NqKLc8AMSbXAF1XAItsVqRlz4I-0AONwDnnXV8J1wexgpWiw3GURMSSGcjP87Vj3yb1sHuuPoL_So0VnCm5uSO6y8D7W91_8w6djsvrFyZNM7rYksMUlO-MzRSqQGI40aaqzP6Q6Ryxxx9mkOZAYk36-TULmZ10AF-45ew
cache-control
no-cache
content-length
469
content-type
application/json
intl
eyJsb2NhbGUiOiJydSIsInRpbWVab25lIjoiRXVyb3BlL01vc2NvdyJ9
origin
https://clip.opus.pro
pragma
no-cache
priority
u=1, i
referer
https://clip.opus.pro/
sec-ch-ua
"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"
sec-ch-ua-mobile
?1
sec-ch-ua-platform
"Android"
sec-fetch-dest
empty
sec-fetch-mode
cors
sec-fetch-site
same-site
user-agent
Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36
x-opus-clip-project-toggle
clip-api
x-opus-crid
a4ZZD
x-opus-did
MEsIb3pwkJy0
x-opus-env
{}
x-opus-lang
en
x-opus-org-id
org_1jhe6sv4lH72EmaspZE8C
x-opus-user-id
user_01KHE6WY7T3TWE7QT9G66GZE8C
x-opus-utm
{"source":"chatgpt.com"}
