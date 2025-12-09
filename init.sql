-- init_db.sql
-- Создание базы данных
SELECT 'CREATE DATABASE skillmatrix'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'skillmatrix')\gexec;

-- Подключение к базе данных
\c skillmatrix;

-- Создание расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Таблица пользователей
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    position VARCHAR(100),
    role VARCHAR(50) NOT NULL CHECK (role IN ('employee', 'manager', 'admin', 'hr')),
    avatar VARCHAR(255),
    phone VARCHAR(20),
    hire_date DATE DEFAULT CURRENT_DATE,
    salary DECIMAL(10, 2),
    performance_rating DECIMAL(3, 2),
    bio TEXT,
    skills_required_rated BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица категорий навыков
CREATE TABLE skill_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(50),
    color VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица навыков
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id UUID REFERENCES skill_categories(id) ON DELETE CASCADE,
    level INTEGER CHECK (level BETWEEN 1 AND 5),
    required_for JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица оценок навыков
CREATE TABLE skill_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    self_score INTEGER CHECK (self_score BETWEEN 1 AND 5),
    manager_score INTEGER CHECK (manager_score BETWEEN 1 AND 5),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    comment TEXT,
    assessed_at DATE DEFAULT CURRENT_DATE,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, skill_id)
);

-- Таблица истории изменений оценок
CREATE TABLE assessment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES skill_assessments(id) ON DELETE CASCADE,
    old_score INTEGER,
    new_score INTEGER,
    changed_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    change_type VARCHAR(50) CHECK (change_type IN ('self_assessment', 'manager_correction', 'system')),
    comment TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица целей
CREATE TABLE goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    deadline DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вставляем категории навыков
INSERT INTO skill_categories (id, name, icon, color, description) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Frontend технологии', 'fa-code', '#6366f1', 'Навыки frontend разработки'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Backend технологии', 'fa-server', '#10b981', 'Навыки backend разработки'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Дизайн', 'fa-paint-brush', '#8b5cf6', 'UI/UX дизайн и прототипирование'),
('dddddddd-dddd-dddd-dddd-dddddddddddd', 'Базы данных', 'fa-database', '#f59e0b', 'Работа с базами данных'),
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'DevOps', 'fa-cloud', '#06b6d4', 'DevOps инструменты и практики'),
('ffffffff-ffff-ffff-ffff-ffffffffffff', 'Гибкие навыки', 'fa-brain', '#ec4899', 'Soft skills и коммуникация');

-- Вставляем навыки
INSERT INTO skills (id, name, description, category_id, level, required_for) VALUES
-- Frontend навыки
('11111111-1111-1111-1111-111111111111', 'JavaScript/ES6+', 'Современный JavaScript', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 5, '["Frontend"]'),
('11111111-1111-1111-1111-111111111112', 'React + hooks', 'Библиотека React с хуками', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 5, '["Frontend"]'),
('11111111-1111-1111-1111-111111111113', 'TypeScript', 'Типизированный JavaScript', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 4, '["Frontend"]'),

-- Backend навыки
('22222222-2222-2222-2222-222222222222', 'Node.js', 'Серверный JavaScript', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 5, '["Backend"]'),
('22222222-2222-2222-2222-222222222223', 'Python/Django', 'Python и фреймворк Django', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 4, '["Backend"]'),

-- Soft skills
('66666666-6666-6666-6666-666666666666', 'Коммуникация', 'Эффективная коммуникация в команде', 'ffffffff-ffff-ffff-ffff-ffffffffffff', 5, '["Frontend", "Backend", "Design", "QA", "HR", "Marketing"]'),
('66666666-6666-6666-6666-666666666667', 'Работа в команде', 'Коллаборация и совместная работа', 'ffffffff-ffff-ffff-ffff-ffffffffffff', 5, '["Frontend", "Backend", "Design", "QA", "HR", "Marketing"]');

-- Вставляем тестовых пользователей (пароль для всех: 123)
INSERT INTO users (id, email, username, full_name, password_hash, department, position, role, avatar, phone, hire_date, salary, performance_rating, bio) VALUES
-- Сотрудник Frontend
('00000000-0000-0000-0000-000000000001', 'user@company.com', 'user', 'Иван Петров', 
 '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',  -- bcrypt hash for '123'
 'Frontend', 'Middle Developer', 'employee', 'IP', '+7 (999) 123-45-67',
 '2023-01-15', 120000, 4.2, 'Frontend разработчик с опытом 3 года. Специализируюсь на React и TypeScript.'),

-- Менеджер Frontend
('00000000-0000-0000-0000-000000000002', 'manager@company.com', 'manager', 'Петр Сидоров',
 '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',  -- bcrypt hash for '123'
 'Frontend', 'Team Lead', 'manager', 'PS', '+7 (999) 987-65-43',
 '2021-03-10', 200000, 4.8, 'Руководитель frontend-отдела. Опыт управления командой 5 лет.'),

-- Администратор HR
('00000000-0000-0000-0000-000000000003', 'admin@company.com', 'admin', 'Анна Иванова',
 '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',  -- bcrypt hash for '123'
 'HR', 'HR Manager', 'admin', 'AI', '+7 (999) 555-12-34',
 '2020-11-05', 180000, 4.5, 'HR специалист с фокусом на развитии персонала и оценке компетенций.');

-- Вставляем оценки навыков
INSERT INTO skill_assessments (id, user_id, skill_id, self_score, manager_score, status, comment, assessed_at) VALUES
-- Оценки для Ивана Петрова (сотрудник Frontend)
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '00000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 4, 4, 'approved', 'Хорошее знание ES6+', '2024-01-15'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', '00000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111112', 3, 3, 'approved', 'Работал с React 1 год', '2024-01-15'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3', '00000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111113', 2, NULL, 'pending', 'Только начал изучение', '2024-01-20'),

-- Оценки для менеджера
('dddddddd-dddd-dddd-dddd-dddddddddd1', '00000000-0000-0000-0000-000000000002', '66666666-6666-6666-6666-666666666666', 5, 5, 'approved', 'Отличные навыки коммуникации', '2024-01-18');

-- Вставляем цели
INSERT INTO goals (id, user_id, title, description, deadline, status, progress, priority) VALUES
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1', '00000000-0000-0000-0000-000000000001', 'Изучить TypeScript', 'Пройди курс TypeScript и примени в проекте', '2024-03-01', 'in_progress', 40, 'high'),
('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2', '00000000-0000-0000-0000-000000000001', 'Повысить навыки React', 'Освоить продвинутые паттерны React', '2024-02-15', 'not_started', 0, 'medium');

-- Создаем функцию для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Создаем триггеры для обновления updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_skills_updated_at BEFORE UPDATE ON skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assessments_updated_at BEFORE UPDATE ON skill_assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Создаем индексы для производительности
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_assessments_user_id ON skill_assessments(user_id);
CREATE INDEX idx_assessments_skill_id ON skill_assessments(skill_id);
CREATE INDEX idx_assessments_status ON skill_assessments(status);
