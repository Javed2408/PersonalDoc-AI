import Icon from '../Common/Icon.jsx'

export default function UserMessage({ message }) {
  const { context } = message
  return (
    <article className="message message--user" aria-label="Your question">
      <p className="message__bubble">{message.content}</p>
      <p className="message__context" title={context.names?.join(', ')}>
        <Icon name="stack" size={12} />
        <span className="visually-hidden">Asked about: </span>
        {context.label}
      </p>
    </article>
  )
}
