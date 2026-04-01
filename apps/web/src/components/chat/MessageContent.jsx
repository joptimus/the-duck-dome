import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from './MessageContent.module.css';

const MENTION_PATTERN = /(^|[\s(])(@[a-z0-9_-]+)/gi;

function splitTextIntoMentionNodes(value) {
  const nodes = [];
  let lastIndex = 0;

  value.replaceAll(MENTION_PATTERN, (match, prefix, mention, offset) => {
    if (offset > lastIndex) {
      nodes.push({ type: 'text', value: value.slice(lastIndex, offset) });
    }
    if (prefix) {
      nodes.push({ type: 'text', value: prefix });
    }
    nodes.push({
      type: 'link',
      url: `mention:${mention.slice(1).toLowerCase()}`,
      children: [{ type: 'text', value: mention }],
    });
    lastIndex = offset + match.length;
    return match;
  });

  if (lastIndex < value.length) {
    nodes.push({ type: 'text', value: value.slice(lastIndex) });
  }

  return nodes.length > 0 ? nodes : [{ type: 'text', value }];
}

function transformMentionNodes(node) {
  if (!node || typeof node !== 'object') return;
  if (!Array.isArray(node.children)) return;

  const nextChildren = [];
  for (const child of node.children) {
    if (child?.type === 'text' && typeof child.value === 'string' && child.value.includes('@')) {
      nextChildren.push(...splitTextIntoMentionNodes(child.value));
      continue;
    }
    transformMentionNodes(child);
    nextChildren.push(child);
  }
  node.children = nextChildren;
}

function remarkMentions() {
  return (tree) => {
    transformMentionNodes(tree);
  };
}

export function MessageContent({ text = '', replyPreview = null, onReplyClick }) {
  return (
    <div className={styles.wrapper}>
      {replyPreview && (
        <button type="button" className={styles.replyPreview} onClick={() => onReplyClick?.(replyPreview.id)}>
          <span className={styles.replyLabel}>Replying to {replyPreview.sender || 'message'}</span>
          <span className={styles.replyText}>{replyPreview.text || `#${replyPreview.id}`}</span>
        </button>
      )}

      <div className={styles.body}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMentions]}
          urlTransform={(url) => (typeof url === 'string' && url.startsWith('mention:') ? url : defaultUrlTransform(url))}
          components={{
            a: ({ href, children, ...props }) => {
              if (typeof href === 'string' && href.startsWith('mention:')) {
                return (
                  <span {...props} className={styles.mention}>
                    {children}
                  </span>
                );
              }
              return <a href={href} {...props} target="_blank" rel="noreferrer" className={styles.link} />;
            },
            code: ({ node, className, children, ...props }) => {
              const isBlockCode = node?.tagName === 'code' && node?.parent?.tagName === 'pre';
              return isBlockCode ? (
                <code {...props} className={`${styles.codeBlock} ${className || ''}`.trim()}>{children}</code>
              ) : (
                <code {...props} className={styles.inlineCode}>{children}</code>
              );
            },
            img: ({ alt, src }) => <img alt={alt || ''} src={src} className={styles.image} />,
            pre: ({ children }) => <pre className={styles.pre}>{children}</pre>,
            p: ({ children }) => <p className={styles.paragraph}>{children}</p>,
            ul: ({ children }) => <ul className={styles.list}>{children}</ul>,
            ol: ({ children }) => <ol className={styles.list}>{children}</ol>,
            blockquote: ({ children }) => <blockquote className={styles.blockquote}>{children}</blockquote>,
          }}
        >
          {text}
        </ReactMarkdown>
      </div>
    </div>
  );
}
