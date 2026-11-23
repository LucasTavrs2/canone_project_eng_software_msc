PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS personagem (
    id            TEXT PRIMARY KEY,
    nome          TEXT NOT NULL,
    papel         TEXT NOT NULL,
    registro_fala TEXT NOT NULL,
    restricoes    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    criado_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fato_canonico (
    id              TEXT NOT NULL,
    personagem_id   TEXT NOT NULL REFERENCES personagem(id) ON DELETE CASCADE,
    texto           TEXT NOT NULL,
    escopo          TEXT NOT NULL DEFAULT 'personagem',
    origem          TEXT NOT NULL DEFAULT 'autorado',   -- autorado | promovido
    ativo           INTEGER NOT NULL DEFAULT 1,         -- desativa, nunca deleta
    turno_origem_id TEXT,                               -- turno de onde foi promovido
    criado_em       TEXT NOT NULL,
    PRIMARY KEY (personagem_id, id)
);

CREATE TABLE IF NOT EXISTS sessao (
    id            TEXT PRIMARY KEY,
    personagem_id TEXT NOT NULL REFERENCES personagem(id) ON DELETE CASCADE,
    titulo        TEXT NOT NULL,
    criada_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turno (
    id                      TEXT PRIMARY KEY,
    sessao_id               TEXT NOT NULL REFERENCES sessao(id) ON DELETE CASCADE,
    indice                  INTEGER NOT NULL,
    fala_jogador            TEXT NOT NULL,
    fala_npc                TEXT NOT NULL,
    veredito                TEXT NOT NULL,      -- consistente | contradiz | indeterminado
    fato_id                 TEXT,               -- só quando veredito = contradiz
    justificativa           TEXT NOT NULL,
    decisao                 TEXT NOT NULL DEFAULT 'pendente',
    latencia_geracao_ms     INTEGER,
    latencia_verificacao_ms INTEGER,
    criado_em               TEXT NOT NULL,
    UNIQUE (sessao_id, indice)
);

CREATE INDEX IF NOT EXISTS idx_fato_personagem ON fato_canonico(personagem_id, ativo);
CREATE INDEX IF NOT EXISTS idx_turno_sessao    ON turno(sessao_id, indice);
