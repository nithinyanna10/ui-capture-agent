"""DOM extraction utilities for web pages."""
from playwright.async_api import Page
from typing import Dict, List, Any
import json


async def extract_dom_tree(page: Page) -> Dict[str, Any]:
    """
    Extract structured DOM tree from the current page.
    
    Args:
        page: Playwright page object
    
    Returns:
        Dictionary containing DOM structure and metadata
    """
    dom_data = await page.evaluate("""
        () => {
            const extractElement = (el) => {
                if (!el) return null;
                
                const rect = el.getBoundingClientRect();
                const styles = window.getComputedStyle(el);
                
                return {
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    classes: Array.from(el.classList || []),
                    text: el.textContent?.trim().substring(0, 100) || null,
                    visible: rect.width > 0 && rect.height > 0 && 
                             styles.display !== 'none' && 
                             styles.visibility !== 'hidden',
                    position: {
                        x: rect.x,
                        y: rect.y,
                        width: rect.width,
                        height: rect.height
                    },
                    attributes: {
                        type: el.type || null,
                        placeholder: el.placeholder || null,
                        role: el.getAttribute('role') || null,
                        'aria-label': el.getAttribute('aria-label') || null,
                    },
                    children: Array.from(el.children).map(extractElement).filter(Boolean)
                };
            };
            
            return {
                url: window.location.href,
                title: document.title,
                root: extractElement(document.body)
            };
        }
    """)
    
    return dom_data


async def extract_interactive_elements(page: Page) -> List[Dict[str, Any]]:
    """
    Extract all interactive elements (buttons, inputs, links).
    
    Args:
        page: Playwright page object
    
    Returns:
        List of interactive elements with their properties
    """
    elements = await page.evaluate("""
        () => {
            const selectors = [
                'button', 'a[href]', 'input', 'select', 'textarea',
                '[role="button"]', '[onclick]', '[tabindex="0"]'
            ];
            
            const interactive = [];
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const styles = window.getComputedStyle(el);
                    
                    if (rect.width > 0 && rect.height > 0 && 
                        styles.display !== 'none' && 
                        styles.visibility !== 'hidden') {
                        interactive.push({
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim() || el.value || el.placeholder || '',
                            id: el.id || null,
                            classes: Array.from(el.classList || []),
                            type: el.type || null,
                            role: el.getAttribute('role') || null,
                            'aria-label': el.getAttribute('aria-label') || null,
                            position: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            }
                        });
                    }
                });
            });
            
            return interactive;
        }
    """)
    
    return elements


async def extract_form_fields(page: Page) -> List[Dict[str, Any]]:
    """
    Extract all form fields (inputs, selects, textareas).
    
    Args:
        page: Playwright page object
    
    Returns:
        List of form fields with their properties
    """
    fields = await page.evaluate("""
        () => {
            const fields = [];
            document.querySelectorAll('input, select, textarea').forEach(el => {
                const rect = el.getBoundingClientRect();
                const styles = window.getComputedStyle(el);
                
                if (rect.width > 0 && rect.height > 0 && 
                    styles.display !== 'none' && 
                    styles.visibility !== 'hidden') {
                    fields.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null,
                        name: el.name || null,
                        id: el.id || null,
                        placeholder: el.placeholder || null,
                        label: el.labels?.[0]?.textContent?.trim() || null,
                        value: el.value || null,
                        required: el.required || false,
                        position: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                }
            });
            return fields;
        }
    """)
    
    return fields

