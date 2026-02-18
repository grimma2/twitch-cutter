opus проверяет возможность доступа клиента при регистрации нового пользователя

https://api.opus.pro/api/client-access-control?q=ipRisk

{
    "data": {
        "detail": {
            "as": "AS213877 u1host ltd",
            "asname": "u1host-as",
            "countryCode": "DE",
            "hosting": false,
            "isp": "u1host ltd",
            "org": "u1host ltd",
            "proxy": false,
            "query": "144.31.68.7"
        },
        "shouldBlock": false,
        "tzClass": "POS",
        "decisionQuality": "BAD_PASS"
    }
}
Сервис верно определил мой vpn и провайдера vps и отцуствие прокси

Так же запросы по этому url

https://api.opus.pro/api/client-access-control?q=project
{"data":{"isActiveSubscriber":false,"productTier":"TRIAL"}}

И самое интересное, запрос на проверку на мульти акаунты. Это мой второй аккаунт, но запрос разрешил доступ

https://api.opus.pro/api/login-users/check-multi-accounts
POST 201 Created

{"access":true}

Так же сервис определяет временные email и не разрешает под ними регистрироваться

При попытке второй раз зарегистрировать под тем же ip я получил такой ответ от их системы защиты

https://api.opus.pro/api/login-users/check-multi-accounts

POST 403 Forbidden
{
    "errorMessage": "You already have an account with a free trial",
    "errorName": "MultiAccountError"
}


Запрос на login

https://api.opus.pro/api/auth/login-profiles?code=452127&codeVerifier=_XwGbAbWQHRLejS3EeMJiiMIIVBfsxy_-Zd4csXh8L_v-ei1Pi3yCO7ho4yxZrjiQUn8Q6-gm9PhY9caFvJX7mgJoNIFx1PtmFnmSv1fLwZK-IPbC0LBezm_v-8Enekv&email=softshorts31%40gmail.com&type=email

GET 200 OK


