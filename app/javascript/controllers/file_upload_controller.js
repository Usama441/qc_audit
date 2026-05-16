import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["input", "zone", "label", "icon"]

  connect() {
    this.inputTarget.addEventListener("change", this.onFileChange.bind(this))
  }

  onFileChange() {
    const file = this.inputTarget.files[0]
    if (file) this.showFile(file)
  }

  dragover(e) {
    e.preventDefault()
    this.zoneTarget.classList.add("border-indigo-500", "bg-indigo-50/50")
    this.zoneTarget.classList.remove("border-gray-200", "bg-gray-50")
  }

  dragleave() {
    this.reset()
  }

  drop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (!file) return

    // Attach to the real file input so Rails picks it up on submit
    const dt = new DataTransfer()
    dt.items.add(file)
    this.inputTarget.files = dt.files

    this.showFile(file)
  }

  showFile(file) {
    this.reset()
    this.iconTarget.innerHTML = `
      <svg class="w-10 h-10 text-indigo-500 mb-3" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5
             a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125
             1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0
             1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/>
      </svg>`
    this.labelTarget.innerHTML = `
      <p class="text-sm font-semibold text-indigo-700 truncate max-w-xs">${file.name}</p>
      <p class="text-xs text-gray-400 mt-0.5">${this.formatSize(file.size)}</p>`
    this.zoneTarget.classList.add("border-indigo-400", "bg-indigo-50/40")
    this.zoneTarget.classList.remove("border-gray-200", "bg-gray-50")
  }

  reset() {
    this.zoneTarget.classList.remove("border-indigo-500", "border-indigo-400", "bg-indigo-50/50", "bg-indigo-50/40")
    this.zoneTarget.classList.add("border-gray-200", "bg-gray-50")
  }

  formatSize(bytes) {
    if (bytes < 1024) return bytes + " B"
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
    return (bytes / (1024 * 1024)).toFixed(1) + " MB"
  }
}
