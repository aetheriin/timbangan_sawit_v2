SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* Sesi login (Admin > Sesi Aktif) disimpan di DB supaya sesi dari semua PC & semua proses server terlihat,
   bisa dipaksa keluar, dan untuk aturan 1 user 1 perangkat. */
IF OBJECT_ID('dbo.sesi_login', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sesi_login (
        sid             VARCHAR(24)  NOT NULL PRIMARY KEY,
        user_id         INT          NOT NULL CONSTRAINT FK_SesiLogin_User REFERENCES dbo.users (id_user),
        ip              VARCHAR(45)  NULL,
        agen            VARCHAR(200) NULL,
        login_at        DATETIME     NOT NULL DEFAULT GETDATE(),
        terakhir_aktif  DATETIME     NOT NULL DEFAULT GETDATE(),
        berakhir_at     DATETIME     NULL,
        alasan          VARCHAR(20)  NULL      -- LOGOUT, IDLE, UMUR_MAKS, PAKSA_KELUAR, PERANGKAT_LAIN, ...
    );
    CREATE INDEX IX_SesiLogin_User ON dbo.sesi_login (user_id, berakhir_at);
    CREATE INDEX IX_SesiLogin_Aktif ON dbo.sesi_login (berakhir_at, terakhir_aktif);
END
GO

/* Riwayat sesi > 90 hari boleh dihapus berkala:
   DELETE FROM dbo.sesi_login WHERE login_at < DATEADD(day, -90, GETDATE()); */
