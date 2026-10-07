import { useRef, useState } from 'react'
import Icon from '../Common/Icon.jsx'

export default function UploadDropzone({ onFiles }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handleFiles = (fileList) => {
    const files = Array.from(fileList ?? [])
    if (files.length) onFiles(files)
  }

  return (
    <div
      className={`dropzone${dragging ? ' dropzone--active' : ''}`}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        handleFiles(event.dataTransfer.files)
      }}
    >
      <button type="button" className="button button--primary" onClick={() => inputRef.current?.click()}>
        <Icon name="upload" />
        Upload PDF
      </button>
      <span className="dropzone__hint">or drop files here</span>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        hidden
        onChange={(event) => {
          handleFiles(event.target.files)
          // Allow choosing the same file again (e.g. a second copy with the same name).
          event.target.value = ''
        }}
      />
    </div>
  )
}
