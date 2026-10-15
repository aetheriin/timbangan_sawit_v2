// ===== EKSPOR TABEL KE EXCEL (.xlsx) / PDF =====
// <button data-on-click="eksporTabel" data-arg="idTbody|xlsx|Judul File">  (format: xlsx / pdf)
// Yang diekspor = baris yang sedang lolos pencarian/filter di layar, SEMUA halaman (bukan hanya halaman aktif).
// Kolom "Aksi" (atau <th data-tanpa-ekspor>) dilewati. Sel dua baris digabung dengan " · ".
// Excel: file .xlsx dibuat langsung di browser (tanpa library); angka "20.800" / "16.240 kg" jadi angka asli.
// PDF: tabel rapi dicetak lewat dialog cetak browser -> pilih "Simpan sebagai PDF" (A4 mendatar).

function dataTabel(idTbody) {
    const tbody = document.getElementById(idTbody);
    const tabel = tbody.closest('table');
    const th = [...tabel.querySelectorAll('thead th')];
    const pakai = th.map(h => !h.hasAttribute('data-tanpa-ekspor') && !['aksi', 'action', 'actions'].includes(h.textContent.trim().toLowerCase()));
    const kepala = th.filter((_, i) => pakai[i]).map(h => h.textContent.trim());
    const baris = [...tbody.rows]
        .filter(tr => tr.cells.length > 1 && !tr.classList.contains('hidden'))
        .map(tr => [...tr.cells].filter((_, i) => pakai[i]).map(teksSel));
    return { kepala, baris };
}

// Teks sel: tiap baris (elemen block / <br>) dipisah " · ", spasi berlebih dibuang
function teksSel(td) {
    const blok = [...td.children].filter(el => getComputedStyle(el).display === 'block');
    const bagian = blok.length > 1 ? blok.map(el => el.textContent) : [td.textContent];
    return bagian.map(t => t.replace(/\s+/g, ' ').trim()).filter(t => t && t !== '-' && t !== '–').join(' · ');
}

// "20.800" / "16.240 kg" / "21,50" -> angka; NIK, no. telp, kode berawalan 0 tetap teks
function keAngka(teks) {
    const t = teks.replace(/\s*(kg|%)$/i, '');
    if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(t) || /^-?([1-9]\d{0,8}|0)(,\d+)?$/.test(t)) {
        return Number(t.replace(/\./g, '').replace(',', '.'));
    }
    return null;
}

function namaFile(judul, ext) {
    const tgl = new Date().toLocaleDateString('sv-SE');     // YYYY-MM-DD
    return `${judul.replace(/[^\w\- ]+/g, '').trim().replace(/\s+/g, '_')}_${tgl}.${ext}`;
}

function eksporTabel(idTbody, format, judul) {
    const data = dataTabel(idTbody);
    judul = t(judul);                                     // judul ikut bahasa tampilan (static/js/i18n.js)
    if (!data.baris.length) { Notif.peringatan('Tidak ada data untuk diekspor'); return; }
    if (format === 'pdf') cetakTabelPdf(judul, data);
    else unduhBlob(buatXlsx(judul, data), namaFile(judul, 'xlsx'));
}

function unduhBlob(blob, nama) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nama;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

// ---------- PDF (lewat cetak browser) ----------
function cetakTabelPdf(judul, { kepala, baris }) {
    const area = document.createElement('div');
    area.id = 'areaCetakTabel';
    const angka = baris[0].map((_, i) => baris.every(r => !r[i] || keAngka(r[i]) != null));
    area.innerHTML = `<h1>${escapeHtml(judul)}</h1>
        <p>${escapeHtml(t(`Dicetak ${new Date().toLocaleString(I18N.lokal)} oleh ${document.body.dataset.user || '-'} · ${baris.length} baris`))}</p>
        <table><thead><tr>${kepala.map((k, i) => `<th${angka[i] ? ' class="kanan"' : ''}>${escapeHtml(k)}</th>`).join('')}</tr></thead>
        <tbody>${baris.map(r => `<tr>${r.map((v, i) => `<td${angka[i] ? ' class="kanan"' : ''}>${escapeHtml(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    document.body.appendChild(area);
    document.body.classList.add('mode-cetak-tabel');
    const judulAsli = document.title;
    document.title = namaFile(judul, 'pdf').replace(/\.pdf$/, '');   // nama file default saat "Simpan sebagai PDF"
    const selesai = () => {
        document.body.classList.remove('mode-cetak-tabel');
        area.remove();
        document.title = judulAsli;
        window.removeEventListener('afterprint', selesai);
    };
    window.addEventListener('afterprint', selesai);
    window.print();
}

// ---------- XLSX (zip tanpa kompresi) ----------
const xmlAman = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '');

function kolomExcel(i) {
    let s = '';
    for (i += 1; i > 0; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + (i - 1) % 26) + s;
    return s;
}

function buatXlsx(judul, { kepala, baris }) {
    const sel = (v, r, c, gaya) => {
        const ref = `${kolomExcel(c)}${r}`;
        const n = gaya === 1 ? null : keAngka(v);
        return n != null ? `<c r="${ref}" s="2"><v>${n}</v></c>`
            : `<c r="${ref}" t="inlineStr"${gaya ? ` s="${gaya}"` : ''}><is><t xml:space="preserve">${xmlAman(v)}</t></is></c>`;
    };
    const lebar = kepala.map((k, i) => Math.min(60, Math.max(k.length, ...baris.map(r => (r[i] || '').length)) + 2));
    const sheet = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<cols>${lebar.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('')}</cols>
<sheetData>
<row r="1">${kepala.map((k, c) => sel(k, 1, c, 1)).join('')}</row>
${baris.map((r, i) => `<row r="${i + 2}">${r.map((v, c) => sel(v, i + 2, c, 0)).join('')}</row>`).join('\n')}
</sheetData>
<autoFilter ref="A1:${kolomExcel(kepala.length - 1)}${baris.length + 1}"/>
</worksheet>`;
    const styles = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.##"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE2E8F0"/></patternFill></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf/></cellStyleXfs>
<cellXfs count="3"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/><xf numFmtId="164" applyNumberFormat="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`;
    const namaSheet = xmlAman(judul.replace(/[\\/?*[\]:]/g, ' ').slice(0, 31));
    const file = {
        '[Content_Types].xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`,
        '_rels/.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`,
        'xl/workbook.xml': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="${namaSheet}" sheetId="1" r:id="rId1"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'${namaSheet.replace(/'/g, "''")}'!$A$1:$${kolomExcel(kepala.length - 1)}$${baris.length + 1}</definedName></definedNames>
</workbook>`,
        'xl/_rels/workbook.xml.rels': `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`,
        'xl/worksheets/sheet1.xml': sheet,
        'xl/styles.xml': styles,
    };
    return new Blob([zipTanpaKompresi(file)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

const TABEL_CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
        t[n] = c >>> 0;
    }
    return t;
})();

function crc32(bytes) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) c = TABEL_CRC[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
}

// Format ZIP "stored": header lokal + data per file, lalu direktori pusat
function zipTanpaKompresi(file) {
    const enc = new TextEncoder();
    const bagian = [], pusat = [];
    let offset = 0;
    const u16 = v => [v & 0xFF, (v >>> 8) & 0xFF];
    const u32 = v => [v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF];
    for (const [nama, isi] of Object.entries(file)) {
        const n = enc.encode(nama), d = enc.encode(isi), crc = crc32(d);
        const umum = [...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc), ...u32(d.length), ...u32(d.length), ...u16(n.length), ...u16(0)];
        const lokal = new Uint8Array([...u32(0x04034b50), ...umum]);
        bagian.push(lokal, n, d);
        pusat.push(new Uint8Array([...u32(0x02014b50), ...u16(20), ...umum, ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(offset)]), n);
        offset += lokal.length + n.length + d.length;
    }
    const ukuranPusat = pusat.reduce((a, b) => a + b.length, 0);
    const jumlah = Object.keys(file).length;
    const akhir = new Uint8Array([...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(jumlah), ...u16(jumlah), ...u32(ukuranPusat), ...u32(offset), ...u16(0)]);
    return new Blob([...bagian, ...pusat, akhir]);
}
