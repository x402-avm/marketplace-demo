import React, { useState, useEffect, useRef } from 'react'
import type { ToolInputSchema, ToolSchemaProperty } from '../types'
import { uploadFile } from '../api'

interface SchemaFormProps {
  schema?: ToolInputSchema
  value?: Record<string, any>
  onChange?: (values: Record<string, any>) => void
  onSubmit?: (values: Record<string, any>) => void
  disabled?: boolean
}

export function isFileLikeField(fieldName: string): boolean {
  const lower = fieldName.toLowerCase()
  return (
    lower.includes('path') ||
    lower.includes('file') ||
    lower.includes('image') ||
    lower.includes('pdf') ||
    lower.includes('video') ||
    lower.includes('audio') ||
    lower.includes('url')
  )
}

export const SchemaForm: React.FC<SchemaFormProps> = ({
  schema,
  value = {},
  onChange,
  onSubmit,
  disabled = false,
}) => {
  const [formData, setFormData] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = { ...value }
    if (schema?.properties) {
      for (const [key, prop] of Object.entries(schema.properties)) {
        if (initial[key] === undefined && prop.default !== undefined) {
          initial[key] = prop.default
        }
      }
    }
    return initial
  })

  const [uploadingField, setUploadingField] = useState<string | null>(null)
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  useEffect(() => {
    setFormData(() => {
      const next: Record<string, any> = { ...value }
      if (schema?.properties) {
        for (const [key, prop] of Object.entries(schema.properties)) {
          if (next[key] === undefined && prop.default !== undefined) {
            next[key] = prop.default
          }
        }
      }
      return next
    })
  }, [schema])

  const updateField = (key: string, val: any) => {
    const updated = { ...formData, [key]: val }
    setFormData(updated)
    if (onChange) {
      onChange(cleanFormValues(schema, updated))
    }
  }

  const handleFileUpload = async (fieldName: string, file: File) => {
    try {
      setUploadingField(fieldName)
      const res = await uploadFile(file)
      updateField(fieldName, res.path)
    } catch (err: any) {
      alert(`Upload failed: ${err.message || err}`)
    } finally {
      setUploadingField(null)
    }
  }

  const cleanFormValues = (
    s?: ToolInputSchema,
    rawValues: Record<string, any> = {}
  ): Record<string, any> => {
    const res: Record<string, any> = {}
    if (!s?.properties) return rawValues

    for (const [key, prop] of Object.entries(s.properties)) {
      const val = rawValues[key]
      if (val === undefined || val === '') continue

      if (prop.type === 'number' || prop.type === 'integer') {
        const parsed = Number(val)
        if (!isNaN(parsed)) {
          res[key] = parsed
        }
      } else if (prop.type === 'boolean') {
        res[key] = Boolean(val)
      } else if (prop.type === 'array') {
        if (Array.isArray(val)) {
          res[key] = val
        } else if (typeof val === 'string') {
          res[key] = val
            .split(',')
            .map((item) => item.trim())
            .filter((item) => item.length > 0)
        }
      } else {
        res[key] = val
      }
    }

    return res
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onSubmit) {
      onSubmit(cleanFormValues(schema, formData))
    }
  }

  if (!schema || !schema.properties || Object.keys(schema.properties).length === 0) {
    return <p className="muted">This tool takes no input.</p>
  }

  const requiredList = schema.required || []

  return (
    <form className="form" onSubmit={handleSubmit}>
      {Object.entries(schema.properties).map(([propName, prop]: [string, ToolSchemaProperty]) => {
        const isRequired = requiredList.includes(propName)
        const isFileLike = isFileLikeField(propName)
        const currentVal = formData[propName] ?? ''

        return (
          <div className="field" key={propName}>
            <label className="field__label" htmlFor={`field-${propName}`}>
              {propName.replace(/_/g, ' ')}
              {isRequired && <span className="field__required" aria-label="required">*</span>}
            </label>
            {prop.description && <span className="field__hint">{prop.description}</span>}

            {prop.enum && prop.enum.length > 0 ? (
              <select
                id={`field-${propName}`}
                data-testid={`field-${propName}`}
                className="input"
                value={currentVal}
                disabled={disabled}
                onChange={(e) => updateField(propName, e.target.value)}
              >
                <option value="">Choose {propName.replace(/_/g, ' ')}</option>
                {prop.enum.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            ) : prop.type === 'boolean' ? (
              <div className="check">
                <input
                  type="checkbox"
                  id={`field-${propName}`}
                  data-testid={`field-${propName}`}
                  checked={Boolean(formData[propName])}
                  disabled={disabled}
                  onChange={(e) => updateField(propName, e.target.checked)}
                />
                <span>Yes</span>
              </div>
            ) : prop.type === 'number' || prop.type === 'integer' ? (
              <input
                type="number"
                id={`field-${propName}`}
                data-testid={`field-${propName}`}
                className="input"
                value={currentVal}
                disabled={disabled}
                step={prop.type === 'integer' ? '1' : 'any'}
                onChange={(e) => updateField(propName, e.target.value)}
              />
            ) : prop.type === 'array' ? (
              <input
                type="text"
                id={`field-${propName}`}
                data-testid={`field-${propName}`}
                className="input"
                placeholder="Separate values with commas"
                value={Array.isArray(currentVal) ? currentVal.join(', ') : currentVal}
                disabled={disabled}
                onChange={(e) => updateField(propName, e.target.value)}
              />
            ) : isFileLike ? (
              <div className="input-row">
                <input
                  type="text"
                  id={`field-${propName}`}
                  data-testid={`field-${propName}`}
                  className="input"
                  placeholder="Upload a file, or paste a URL or server path"
                  value={currentVal}
                  disabled={disabled}
                  onChange={(e) => updateField(propName, e.target.value)}
                />
                <input
                  type="file"
                  ref={(el) => {
                    fileInputRefs.current[propName] = el
                  }}
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileUpload(propName, e.target.files[0])
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn btn--quiet"
                  disabled={disabled || uploadingField === propName}
                  onClick={() => fileInputRefs.current[propName]?.click()}
                >
                  {uploadingField === propName ? 'Uploading' : 'Upload'}
                </button>
              </div>
            ) : (
              <input
                type="text"
                id={`field-${propName}`}
                data-testid={`field-${propName}`}
                className="input"
                value={currentVal}
                disabled={disabled}
                onChange={(e) => updateField(propName, e.target.value)}
              />
            )}
          </div>
        )
      })}
    </form>
  )
}
