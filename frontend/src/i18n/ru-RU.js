import wihApi from './wihApi.ru-RU.js';
import pages from './pages.ru-RU.js';
import assets from './assets.ru-RU.js';
import tasks from './tasks.ru-RU.js';

export default {
  wihApi,
  pages,
  assets,
  tasks,
  "language": {
    "select": "Язык интерфейса"
  },
  "common": {
    "cancel": "Отмена",
    "unknownError": "Неизвестная ошибка"
  },
  "login": {
    "username": "Имя пользователя",
    "password": "Пароль",
    "usernameRequired": "Введите имя пользователя.",
    "passwordRequired": "Введите пароль.",
    "signIn": "Войти",
    "success": "Вход выполнен",
    "invalidCredentials": "Ошибка входа: неверное имя пользователя или пароль",
    "failed": "Ошибка входа: {reason}",
    "networkError": "Ошибка запроса. Проверьте консоль или состояние службы."
  },
  "navigation": {
    "dashboard": "Обзор",
    "assetGroups": "Группы активов",
    "tasks": "Задачи",
    "assetSearch": "Поиск активов",
    "schedules": "Планы и расписания",
    "github": "Мониторинг GitHub",
    "pocs": "Управление PoC",
    "fingerprints": "Отпечатки",
    "policies": "Политики",
    "settings": "Настройки системы",
    "taskDetail": "Подробности задачи",
    "assetGroupDetail": "Подробности группы активов",
    "policyDetail": "Подробности политики"
  },
  "layout": {
    "toggleInterface": "Нажмите, чтобы скрыть или показать интерфейс",
    "sortMenu": "Перетащите для изменения порядка",
    "theme": "Тема",
    "cyan": "Голубой ARL",
    "blue": "Синий AntD",
    "green": "Зелёный Geek",
    "orange": "Оранжевый Volcano",
    "pink": "Розовый",
    "background": "Пользовательский фон",
    "darkMode": "Тёмный режим",
    "basicAuthEnabled": "Basic Auth включён (нажмите для переключения)",
    "basicAuthDisabled": "Basic Auth отключён (нажмите для переключения)",
    "basicAuthOffline": "Служба управления Basic Auth недоступна",
    "mcp": "AI-помощник (MCP)",
    "userSettings": "Настройки и действия пользователя",
    "signOut": "Выйти",
    "resetMenu": "Сбросить порядок меню",
    "resetMenuConfirm": "Восстановить стандартный порядок бокового меню?",
    "resetMenuOk": "Восстановить по умолчанию",
    "resetMenuSuccess": "Стандартный порядок меню восстановлен"
  },
  "account": {
    "changePassword": "Изменить пароль",
    "confirmChange": "Изменить пароль",
    "oldPassword": "Текущий пароль",
    "newPassword": "Новый пароль",
    "confirmPassword": "Подтверждение нового пароля",
    "oldPlaceholder": "Введите текущий пароль",
    "newPlaceholder": "Введите новый пароль",
    "confirmPlaceholder": "Введите новый пароль повторно",
    "confirmRequired": "Подтвердите новый пароль.",
    "mismatch": "Новые пароли не совпадают.",
    "oldRequired": "Введите текущий пароль.",
    "newRequired": "Введите новый пароль.",
    "changed": "Пароль изменён. Войдите снова.",
    "failed": "Не удалось изменить пароль"
  },
  "request": {
    "sessionExpired": "Сеанс истёк или недействителен. Войдите снова.",
    "networkError": "Ошибка запроса. Проверьте серверную службу."
  }
};
