import { useEffect, useMemo, useRef, useState } from 'react';
import { downloadFile, fetchFiles, uploadFile } from './api/client';
import type { FileItem } from './types';
import './App.css';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size < 10 ? 1 : 0)} ${units[unitIndex]}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}

function FileIcon({ contentType }: { contentType: string }) {
  const image = contentType.startsWith('image/');
  const archive = contentType.includes('zip') || contentType.includes('compressed');
  const label = image ? 'IMG' : archive ? 'ZIP' : contentType.includes('pdf') ? 'PDF' : 'DOC';
  return (
    <span className={`file-icon ${image ? 'file-icon-image' : archive ? 'file-icon-archive' : ''}`} aria-hidden="true">
      {label}
    </span>
  );
}

export default function App() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    fetchFiles()
      .then((response) => {
        if (active) setFiles(response.items);
      })
      .catch((error: unknown) => {
        if (active) setNotice({ kind: 'error', message: messageFromError(error) });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const visibleFiles = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('it');
    return files.filter((file) => file.name.toLocaleLowerCase('it').includes(query));
  }, [files, search]);

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setUploading(true);
    setNotice(null);
    try {
      const uploaded = await uploadFile(file);
      setFiles((current) => [uploaded, ...current]);
      setNotice({ kind: 'success', message: `${uploaded.name} was uploaded successfully.` });
    } catch (error) {
      setNotice({ kind: 'error', message: messageFromError(error) });
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(file: FileItem) {
    setDownloadingId(file.id);
    setNotice(null);
    try {
      await downloadFile(file);
      setNotice({ kind: 'success', message: `Download di ${file.name} avviato.` });
    } catch (error) {
      setNotice({ kind: 'error', message: messageFromError(error) });
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Cloudspace home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>cloudspace</span>
        </a>
        <div className="account">
          <span className="account-avatar" aria-hidden="true">A</span>
          <span className="account-name">Admin</span>
        </div>
      </header>

      <section className="content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h1>Your files</h1>
            <p className="subtitle">All your documents, organized in one place.</p>
          </div>
          <div className="upload-control">
            <input
              ref={inputRef}
              className="visually-hidden"
              type="file"
              aria-label="Choose a file to upload"
              onChange={handleUpload}
              disabled={uploading}
            />
            <button className="button button-primary" type="button" onClick={() => inputRef.current?.click()} disabled={uploading}>
              <span className="plus-icon" aria-hidden="true">+</span>
              {uploading ? 'Uploading…' : 'Upload file'}
            </button>
            <span className="upload-hint">Up to 100 MB</span>
          </div>
        </div>

        {notice && (
          <div className={`notice notice-${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
            <span>{notice.kind === 'success' ? '✓' : '!'}</span>
            <p>{notice.message}</p>
            <button type="button" aria-label="Dismiss notification" onClick={() => setNotice(null)}>×</button>
          </div>
        )}

        <section className="files-panel" aria-label="Files">
          <div className="panel-toolbar">
            <div className="file-count">
              <h2>Recent files</h2>
              <span>{files.length}</span>
            </div>
            <label className="search-box">
              <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.7" cy="8.7" r="5.8" /><path d="m13 13 4 4" /></svg>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search files" aria-label="Search files" />
            </label>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Last modified</th>
                  <th scope="col">Size</th>
                  <th scope="col">Version</th>
                  <th scope="col"><span className="visually-hidden">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td className="table-message" colSpan={5}>Loading files…</td></tr>
                ) : visibleFiles.length ? visibleFiles.map((file) => (
                  <tr key={file.id}>
                    <td data-label="Name">
                      <div className="file-name-cell">
                        <FileIcon contentType={file.content_type} />
                        <div className="file-name-text">
                          <span className="file-name">{file.name}</span>
                          <span className="file-owner">by {file.owner.username}</span>
                        </div>
                      </div>
                    </td>
                    <td data-label="Last modified" className="muted-cell">{formatDate(file.updated_at)}</td>
                    <td data-label="Size" className="muted-cell">{formatSize(file.size_bytes)}</td>
                    <td data-label="Version"><span className="version-pill">v{file.current_version}</span></td>
                    <td data-label="Azioni" className="action-cell">
                      {file.permissions.can_read && (
                        <button
                          className="button button-download"
                          type="button"
                          onClick={() => void handleDownload(file)}
                          disabled={downloadingId === file.id}
                          aria-label={`Download ${file.name}`}
                        >
                          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.5v9m0 0 3.5-3.5M10 11.5 6.5 8M3.5 12.5v3A1.5 1.5 0 0 0 5 17h10a1.5 1.5 0 0 0 1.5-1.5v-3" /></svg>
                          <span>{downloadingId === file.id ? 'Downloading…' : 'Download'}</span>
                        </button>
                      )}
                    </td>
                  </tr>
                )) : (
                  <tr><td className="table-message" colSpan={5}>{search ? 'No files match your search.' : 'There are no files yet. Upload your first document.'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <footer className="panel-footer">
            <span>{search ? `${visibleFiles.length} of ${files.length} files` : `${files.length} files total`}</span>
            <span className="secure-label"><span aria-hidden="true">●</span> Secure storage</span>
          </footer>
        </section>
        <p className="page-footnote">Your files are only accessible to you and the people you share them with.</p>
      </section>
    </main>
  );
}

function messageFromError(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error && typeof error.message === 'string') {
    return error.message;
  }
  return 'Something went wrong. Please try again shortly.';
}
