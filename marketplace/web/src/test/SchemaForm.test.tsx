import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { SchemaForm } from '../components/SchemaForm'
import type { ToolInputSchema } from '../types'

describe('SchemaForm Component', () => {
  const sampleSchema: ToolInputSchema = {
    type: 'object',
    required: ['text_param', 'num_param'],
    properties: {
      text_param: {
        type: 'string',
        description: 'A text field',
      },
      num_param: {
        type: 'number',
        description: 'A number field',
      },
      int_param: {
        type: 'integer',
        description: 'An integer field',
      },
      bool_param: {
        type: 'boolean',
        description: 'A boolean flag',
      },
      enum_param: {
        type: 'string',
        enum: ['fast', 'high_quality', 'balanced'],
        description: 'Selection mode',
      },
      array_param: {
        type: 'array',
        items: { type: 'string' },
        description: 'List of tags',
      },
      image_path: {
        type: 'string',
        description: 'Path or URL to input image',
      },
    },
  }

  it('renders all schema types correctly with data-testid attributes', () => {
    render(<SchemaForm schema={sampleSchema} />)

    // Text field
    expect(screen.getByTestId('field-text_param')).toBeInTheDocument()
    // Number field
    expect(screen.getByTestId('field-num_param')).toBeInTheDocument()
    // Integer field
    expect(screen.getByTestId('field-int_param')).toBeInTheDocument()
    // Boolean checkbox
    expect(screen.getByTestId('field-bool_param')).toBeInTheDocument()
    // Enum select
    expect(screen.getByTestId('field-enum_param')).toBeInTheDocument()
    // Array text input
    expect(screen.getByTestId('field-array_param')).toBeInTheDocument()
    // File-like field with upload button
    expect(screen.getByTestId('field-image_path')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /upload/i })).toBeInTheDocument()
  })

  it('produces the right typed args object when inputs change', () => {
    const handleChange = vi.fn()
    render(<SchemaForm schema={sampleSchema} onChange={handleChange} />)

    // Change string
    fireEvent.change(screen.getByTestId('field-text_param'), {
      target: { value: 'Hello world' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ text_param: 'Hello world' })
    )

    // Change number
    fireEvent.change(screen.getByTestId('field-num_param'), {
      target: { value: '42.5' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ num_param: 42.5 })
    )

    // Change integer
    fireEvent.change(screen.getByTestId('field-int_param'), {
      target: { value: '10' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ int_param: 10 })
    )

    // Change boolean checkbox
    fireEvent.click(screen.getByTestId('field-bool_param'))
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ bool_param: true })
    )

    // Change enum select
    fireEvent.change(screen.getByTestId('field-enum_param'), {
      target: { value: 'high_quality' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ enum_param: 'high_quality' })
    )

    // Change array (comma-separated string)
    fireEvent.change(screen.getByTestId('field-array_param'), {
      target: { value: 'alpha, beta, gamma' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ array_param: ['alpha', 'beta', 'gamma'] })
    )

    // Change file-like path
    fireEvent.change(screen.getByTestId('field-image_path'), {
      target: { value: '/tests/fixtures/sample.jpg' },
    })
    expect(handleChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ image_path: '/tests/fixtures/sample.jpg' })
    )
  })

  it('renders required marks on required fields', () => {
    const { container } = render(<SchemaForm schema={sampleSchema} />)
    const requiredStars = container.querySelectorAll('.field__required')
    // Both text_param and num_param are required
    expect(requiredStars.length).toBe(2)
  })

  it('displays empty message when schema has no properties', () => {
    render(<SchemaForm schema={{ type: 'object', properties: {} }} />)
    expect(screen.getByText(/takes no input/i)).toBeInTheDocument()
  })
})
